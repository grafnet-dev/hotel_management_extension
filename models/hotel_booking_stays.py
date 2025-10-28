import json

# import logging
import logging

_logger = logging.getLogger(__name__)
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time
from ..constants.booking_stays_state import STAY_STATES
from ..logging_config import eclc_logger as _logger
from ..logging_booking import booking_logger as _logger_booking
from ..utils.logger_utils import setup_logger

early_late_logger = setup_logger("hotel.early_late", "early_late.log")
# === LOGGER PERSONNALISÉ POUR LES SÉJOURS ===
hotel_stay_logger = setup_logger(
    name="hotel.booking.stay",
    log_file="stay.log",
    log_dir="."  # 👈 adapte ce chemin selon ton serveur (ou juste "." si local)
)

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)


class HotelBookingStayS(models.Model):
    _name = "hotel.booking.stay"
    _description = "Séjour individuel de chaque reservation (booking)"
    # _rec_name = 'room_id' -> ici à faire de recherche et comprendre son utilité
    product_id = fields.Many2one(
        "product.product",
        string="Produit de facturation",
        domain=[("type", "=", "service")],
        help="Produit Odoo utilisé pour générer les lignes de facture de ce type de chambre.",
    )
    # Infos occupants
    occupant_ids = fields.Many2many(
        "res.partner",
        "hotel_booking_stay_res_partner_rel",
        "stay_id",
        "partner_id",
        string="Occupants",
        help="Occupants of the room for this stay",
    )

    occupant_names = fields.Char(
        string="Occupants Names",
        compute="_compute_occupant_names",
        store=True,
        help="List of occupant names, used for display purposes",
    )

    # Identification & Lien
    booking_id = fields.Many2one(
        "room.booking", string="Booking", help="Indicates the Room", ondelete="cascade"
    )
    room_type_id = fields.Many2one(
        "hotel.room.type",
        string="Type de Chambre",
        help="Indicates the Room Type",
        required=True,
    )
    room_id = fields.Many2one(
        "hotel.room",
        string="Chambre",
        help="Indicates the Room",
    )
    room_name = fields.Char(
        related="room_id.name", string="Nom de la chambre", readonly=True
    )
    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        help="Type de réservation sélectionné pour cette chambre",
    )
    # Dates & Horaires
    # # Jours choisis par le user
    booking_start_date = fields.Date(
        string="Date de début de réservation (choisie)",
        help="Date  de début utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )
    booking_end_date = fields.Date(
        string="Date de fin de réservation (choisie)",
        help="Date de fin utilisée pour pour calculer automatiquement les horaires de check-in et check-out",
    )

    ## Datetimes calculés ou saisis (logique standard)
    planned_checkin_date = fields.Datetime(
        string="Planned Check-in",
        help="Heure prévue de check-in calculée automatiquement.",
        compute="_compute_checkin_checkout",
        store=True,
    )

    planned_checkout_date = fields.Datetime(
        string="Planned Check-out",
        help="Heure prévue de check-out calculée automatiquement.",
        compute="_compute_checkin_checkout",
        store=True,
    )

    ## Datetimes effectifs (après ajustement EC/LC)
    actual_checkin_date = fields.Datetime(
        string="Actual Check-in",
        help="Heure réelle de check-in (peut être ajustée par EC/LC).",
        compute="_compute_actual_checkin_checkout",
        store=True,
    )

    actual_checkout_date = fields.Datetime(
        string="Actual Check-out",
        help="Heure réelle de check-out (peut être ajustée par EC/LC).",
        compute="_compute_actual_checkin_checkout",
        store=True,
    )
    ##champs ajoutés pour la gestion dyanmque de la vue dans le xml
    is_flexible_reservation = fields.Boolean(
        related="reservation_type_id.is_flexible",
        store=True,
    )

    # Gestion du early check-in et late check-out

    early_checkin_requested = fields.Boolean("Early Check-in demandé")
    late_checkout_requested = fields.Boolean("Late Check-out demandé")
    ### Heure exacte demandée par le client early checkin
    requested_checkin_datetime = fields.Datetime(
        string="Heure demandée Check-in",
        help="Datetime d'arrivée demandée par le client pour l'early check-in.",
    )
    requested_checkout_datetime = fields.Datetime(
        string="Heure demandée Check-out",
        help="Datetime de départ demandée par le client pour le late check-out.",
    )
    # Écart calculé automatiquement (pour reporting)
    difference_hours = fields.Float(
        string="Écart demandé (heures)",
        compute="_compute_difference_hours",
        store=True,
        help="Nombre d'heures d'écart demandé entre l'heure prévue et l'heure souhaitée.",
    )

    early_difference_hours = fields.Float(
        string="Écart Early (heures)",
        compute="_compute_difference_hours",
        store=True,
    )
    late_difference_hours = fields.Float(
        string="Écart Late (heures)",
        compute="_compute_difference_hours",
        store=True,
    )
    # Historique / compatibilité
    request_type = fields.Selection(
        [("early", "Early Check-in"), ("late", "Late Check-out")],
        string="Type de demande horaire",
        compute="_compute_request_type",
        store=False,
    )
    time_engine_trace = fields.Text(
        string="Trace moteur horaire (JSON)",
        help="Historique des évaluations early/late (append-only, à visée d'audit/diagnostic).",
    )
    extra_night_required = fields.Boolean(
        string="Nuit supplémentaire requise", default=False
    )
    # Distinguer flexible manuel vs automatique
    is_manual_flexible = fields.Boolean(
        "Flexible sélectionné manuellement",
        help="True si l'utilisateur a directement sélectionné le type flexible, False si requalification automatique",
    )

    eclc_status = fields.Selection(
        [
            ("accepted", "Acceptée"),
            ("refused", "Refusée"),
            ("pending", "En attente"),
        ],
        string="Statut EC/LC",
    )

    EC_LC_SELECTION = [
        ("early_fee", "Early check-in payant"),
        ("late_fee", "Late check-out payant"),
        ("extra_night", "Nuit supplémentaire"),
        ("invalid_request", "Requête invalide"),
    ]

    early_pricing_mode = fields.Selection(
        EC_LC_SELECTION,
        string="Mode tarifaire EC",
        compute="_compute_actual_checkin_checkout",
        store=True,
    )

    late_pricing_mode = fields.Selection(
        EC_LC_SELECTION,
        string="Mode tarifaire LC",
        compute="_compute_actual_checkin_checkout",
        store=True,
    )

    early_checkin_price = fields.Float(
        string="Prix Early Check-in", default=0.0, readonly=True
    )
    late_checkout_price = fields.Float(
        string="Prix Late Checkout", default=0.0, readonly=True
    )

    # consommations du séjour
    need_food = fields.Boolean(
        default=False,
        string="Besoin de nourriture ?",
        help="Check if a Event to be added with" " the Booking",
    )
    food_order_line_ids = fields.One2many(
        "food.booking.line", "booking_id", string="Food Order Lines", copy=True
    )

    need_service = fields.Boolean(
        default=False,
        string="Besoin de services ?",
        help="Check if a Service to be added with" " the Stay",
    )
    service_booking_line_ids = fields.One2many(
        "service.booking.line", "booking_id", string="Service Stay Lines", copy=True
    )

    need_fleet = fields.Boolean(
        default=False,
        string="Besoin de véhicule ?",
        help="Check if a Fleet to be added with" " the Stay",
    )
    fleet_booking_line_ids = fields.One2many(
        "fleet.booking.line",
        "booking_id",
        string="Fleet Stay Lines",
        copy=True,
        help="Check if a Event to be added with" " the Stay",
    )

    need_event = fields.Boolean(
        default=False,
        string="Participer à un événement ? ",
        help="Check if a Event to be added with" " the Stay",
    )
    event_booking_line_ids = fields.One2many(
        "event.booking.line", "booking_id", string="Event Stay Lines", copy=True
    )

    # Prix & Facturation -> à définir les champs nécessaires plus tard et logique de calcul
    ## Durée & Unité
    uom_qty = fields.Float(
        string="Duration",
        help="The quantity converted into the UoM used by " "the product",
        readonly=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="This will set the unit of measure used",
        readonly=True,
    )

    currency_id = fields.Many2one(
        string="Currency",
        related="booking_id.pricelist_id.currency_id",
        help="The currency used",
    )
    pricing_rule_id = fields.Many2one(
        "hotel.pricing.rule",
        string="Règle tarifaire appliquée",
        readonly=True,
        copy=False,
    )

    pricing_price_base = fields.Float(
        string="Prix de base , Prix de la chambre sans ec/lc ", readonly=True
    )

    pricing_unit = fields.Char(
        string="Unité de tarification", readonly=True
    )  # night, hour, slot
    pricing_unit_price = fields.Float(
        string="Prix unitaire", readonly=True
    )  # prix unitaire
    pricing_quantity = fields.Float(string="Quantité", readonly=True)  # nombre d’unités

    room_price_total = fields.Monetary(
        string="Prix chambre+ec/lc",
        compute="_compute_room_price_total",
        store=True,
        currency_field="currency_id",
    )

    pricing_adjustments = fields.Text(
        string="Ajustements appliqués",
        readonly=True,
        help="Stocke en JSON les détails des ajustements (supplément extra guest, etc.)",
    )
    pricing_supplements = fields.Text(
        string="Supplements (JSON)",
        readonly=True,
        help="Suppléments appliqués (early/late fees, extras...) en JSON.",
    )

    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        help="Total Price excluding Tax",
        store=True,
    )

    price_tax = fields.Float(
        string="Total Tax",
        compute="_compute_price_subtotal",
        help="Tax Amount",
        store=True,
    )
    price_total = fields.Float(
        string="Total",
        compute="_compute_price_subtotal",
        help="Total Price including Tax",
        store=True,
    )

    early_checkin_fee = fields.Float(string="Montant Arrivée Tôt", readonly=True)
    late_checkout_fee = fields.Float(string="Montant Départ Tardif ", readonly=True)

    invoice_ids = fields.One2many(
        "account.move",
        "stay_id",
        string="Factures",
    )
    financial_summary_details = fields.Text(
        string="Résumé financier (JSON)",
        readonly=True,
        help="Détails financiers du séjour (base, ajustements, suppléments, remises, taxes, total)",
    )

    state = fields.Selection(
        selection=[
            (STAY_STATES["PENDING"], "En attente"),
            (STAY_STATES["ONGOING"], "En cours"),
            (STAY_STATES["COMPLETED"], "Terminé"),
            (STAY_STATES["CANCELLED"], "Annulé"),
        ],
        string="État",
        default=STAY_STATES["PENDING"],
        tracking=True,
    )

    availability_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("available", "Available"),
            ("unavailable", "Unavailable"),
            ("not_checked", "Not Checked"),
        ],
        string="Availability Status",
        default="unknown",
        readonly=False,
    )

    availability_message = fields.Char(
        string="Availability Message",
        readonly=False,
    )
    
    @api.model
    def create(self, vals):
        """Quand un séjour est créé :
        - Si le booking est temporaire → le rendre permanent
        - Si des occupants sont renseignés → définir le partner du booking
        """
        stay = super().create(vals)
        booking = stay.booking_id

        if booking:
            # 🔹 Convertir le booking temporaire en permanent
            if booking.is_temporary:
                booking.is_temporary = False
                _logger.info(f"✅ Booking {booking.name} converti en permanent (lié au séjour {stay.id})")

            # 🔹 Si occupants → prendre le premier comme client
            if stay.occupant_ids:
                booking.partner_id = stay.occupant_ids[0].id
                _logger.info(f"👤 Booking {booking.name} lié au client {booking.partner_id.name}")

        return stay
    
  

    
    @api.depends("occupant_ids")
    def _compute_partner_id(self):
        """Déduit le client principal à partir du premier occupant."""
        for stay in self:
            stay.partner_id = stay.occupant_ids[:1].id if stay.occupant_ids else False

    

    @api.onchange("room_type_id")
    def _onchange_room_type_id(self):
        if self.room_id and self.room_id.room_type_id != self.room_type_id:
            self.room_id = False

    # ouvrir un modal pour la fiche de police
    def action_start_checkin_wizard(self):
        self.ensure_one()  # sécurité si la méthode est appelée sur plusieurs enregistrements

        # On récupère occupant_names
        occupant_name = self.occupant_names or ""
        parts = occupant_name.strip().split(" ", 1)
        first_name = parts[0] if len(parts) > 0 else ""
        last_name = parts[1] if len(parts) > 1 else ""

        return {
            "type": "ir.actions.act_window",
            "name": "Fiche de Police",
            "res_model": "hotel.police.form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_stay_id": self.id,
                "default_booking_id": self.booking_id.id,
                "default_first_name": first_name,
                "default_last_name": last_name,
                "default_room_id": self.room_id.id,
            },
        }

    def action_open_police_form(self):
        self.ensure_one()

        # Vérifier si une fiche de police existe déjà
        police_form = self.env["hotel.police.form"].search(
            [("stay_id", "=", self.id)], limit=1
        )

        # Retourner l'action pour ouvrir la fiche police
        return {
            "type": "ir.actions.act_window",
            "res_model": "hotel.police.form",
            "view_mode": "form",
            "res_id": police_form.id,
            "target": "current",  # ou 'new' si tu veux en pop-up modal
        }

    def action_print_police_form(self):
        self.ensure_one()

        # Vérifier si une fiche existe déjà
        police_form = self.env["hotel.police.form"].search(
            [("stay_id", "=", self.id)], limit=1
        )

        # Vérifier si le rapport existe
        try:
            report = self.env.ref(
                "hotel_management_extension.action_report_hotel_police_form"
            )
            return report.report_action(police_form)
        except ValueError as e:
            # Log l'erreur et essayez une alternative
            _logger.error(f"Rapport non trouvé: {e}")
            raise UserError(
                "Le rapport de fiche de police n'est pas disponible. Veuillez contacter l'administrateur."
            )

  

    # Méthode pour calculer les noms des occupants
    @api.depends("occupant_ids")
    def _compute_occupant_names(self):
        for stay in self:
            stay.occupant_names = (
                ", ".join(stay.occupant_ids.mapped("name")) if stay.occupant_ids else ""
            )

    def action_start(self):
        self.ensure_one()
        self.state = STAY_STATES["ONGOING"]

    def action_checkout(self):
        self.ensure_one()
        _logger.info("➡️ [CHECKOUT] Début du process checkout pour stay=%s", self.id)

        # Étape 1 : Passage en COMPLETED
        self.state = STAY_STATES["COMPLETED"]
        _logger.info("✅ [CHECKOUT] Stay=%s marqué COMPLETED", self.id)
        _logger.info(
            "[CHECKOUT] stay=%s | summary_before_report=%s",
            self.id,
            self.financial_summary_details,
        )

        # Étape 2 : Générer la facture PDF
        return self.env.ref(
            "hotel_management_extension.action_report_hotel_stay_invoice"
        ).report_action(self)

    def action_cancel(self):
        self.state = STAY_STATES["CANCELLED"]

    def _set_default_uom_id(self):
        return self.env.ref("uom.product_uom_day")

    # calcul automatique de la durée (methode à adapter plus tard)
    @api.depends("planned_checkin_date", "planned_checkout_date")
    def _compute_duration(self):
        for rec in self:
            if rec.planned_checkin_date and rec.planned_checkout_date:
                diff = rec.planned_checkout_date - rec.planned_checkin_date
                rec.uom_qty = diff.days + (1 if diff.total_seconds() > 0 else 0)
            else:
                rec.uom_qty = 0

    ###############################################
    # Gestion de dates
    ###############################################
    @api.depends(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _compute_checkin_checkout(self):
        for rec in self:
            _logger_booking.debug(
                "🟢 _compute_checkin_checkout déclenché pour stay %s", rec.id
            )
            self._compute_dates_logic(rec)
            _logger_booking.debug(
                "🟢 _compute_checkin_checkout terminé pour stay %s", rec.id
            )

    @api.onchange(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _onchange_dates_and_type(self):
        """
        Calcul instantané + vérification de disponibilité en temps réel.
        Affiche un warning dès que les dates sont saisies.
        VERSION AMÉLIORÉE : Gère mieux les cas edge et les erreurs.
        """
        for rec in self:
            _logger_booking.debug(
                "🟠 _onchange_dates_and_type déclenché pour stay %s", rec.id
            )

            # 1) Calcul des dates planned
            self._compute_dates_logic(rec)

            # 2) Vérification de disponibilité si toutes les données sont présentes
            if (
                rec.room_type_id
                and rec.planned_checkin_date
                and rec.planned_checkout_date
            ):

                _logger_booking.info(
                    "[ONCHANGE] Vérification disponibilité | type=%s | in=%s | out=%s | flexible=%s",
                    rec.room_type_id.name,
                    rec.planned_checkin_date,
                    rec.planned_checkout_date,
                    rec.is_flexible_reservation,
                )

                return self._check_and_warn_availability(rec)
            else:
                _logger_booking.debug(
                    "[ONCHANGE] Skip vérification | has_type=%s | has_dates=%s | is_flexible=%s",
                    bool(rec.room_type_id),
                    bool(rec.planned_checkin_date and rec.planned_checkout_date),
                    rec.is_flexible_reservation,
                )

    # ========================-Methodes utilitaires==================#
    def _compute_dates_logic(self, rec):
        """
        Recalcule automatiquement planned_checkin_date et planned_checkout_date
        en fonction du type de réservation.
        """

        _logger_booking.debug("is_flexible_reservation=%s", rec.is_flexible_reservation)
        _logger_booking.debug("➡️ _compute_dates_logic appelé pour stay %s", rec.id)

        _logger_booking.debug("➡️ _compute_dates_logic appelé pour stay %s", rec.id)
        _logger_booking.debug(
            "📅 Paramètres de départ : start=%s | end=%s | type=%s | flexible=%s",
            rec.booking_start_date,
            rec.booking_end_date,
            rec.reservation_type_id and rec.reservation_type_id.name,
            rec.is_flexible_reservation,
        )
        # Si flexible → ne rien modifier
        if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
            _logger_booking.debug(
                "ℹ️ Réservation flexible, pas de calcul auto. On garde les dates existantes."
            )
            return

        # Validation des données de base
        if (
            not rec.booking_start_date
            or not rec.booking_end_date
            or not rec.reservation_type_id
        ):
            _logger_booking.debug(
                "❌ Données insuffisantes : start=%s end=%s type=%s",
                rec.booking_start_date,
                rec.booking_end_date,
                rec.reservation_type_id,
            )
            return

        # Réinitialiser avant de recalculer
        rec.planned_checkin_date = False
        rec.planned_checkout_date = False

        # Recherche du slot
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_type_id", "=", rec.room_type_id.id),
                ("reservation_type_id", "=", rec.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            _logger_booking.warning(
                "⚠️ Aucun slot trouvé pour room_type=%s, resa_type=%s",
                rec.room_type_id.id,
                rec.reservation_type_id.id,
            )
            return

        # Calcul normal
        rec.planned_checkin_date = datetime.combine(
            rec.booking_start_date, float_to_time(slot.checkin_time)
        )
        rec.planned_checkout_date = datetime.combine(
            rec.booking_end_date, float_to_time(slot.checkout_time)
        )

        if (
            rec.reservation_type_id.code == "classic"
            and rec.planned_checkout_date <= rec.planned_checkin_date
        ):
            rec.planned_checkout_date += timedelta(days=1)
            _logger_booking.debug(
                "↪️ Correction appliquée (+1 jour) -> checkout=%s",
                rec.planned_checkout_date,
            )

        _logger_booking.debug(
            "✅ Dates calculées: checkin=%s checkout=%s",
            rec.planned_checkin_date,
            rec.planned_checkout_date,
        )

    def _check_and_warn_availability(self, rec):
        """
        Méthode utilitaire pour vérifier la disponibilité et retourner un warning.
        VERSION AMÉLIORÉE : Meilleure gestion des erreurs et messages plus clairs.
        """
        buffer_hours = 0.5

        try:
            # --- Validation des prérequis ---
            if not rec.room_type_id:
                _logger_booking.debug("⚠️ Vérification annulée : room_type_id manquant.")
                return {
                    "warning": {
                        "title": _("⚠️ Type de chambre manquant"),
                        "message": _(
                            "Veuillez sélectionner un type de chambre avant de vérifier la disponibilité."
                        ),
                    }
                }

            if not rec.planned_checkin_date or not rec.planned_checkout_date:
                _logger_booking.debug(
                    "⚠️ Vérification annulée : dates planned manquantes."
                )
                return {
                    "warning": {
                        "title": _("⚠️ Dates manquantes"),
                        "message": _(
                            "Veuillez d'abord définir les dates d'arrivée et de départ avant de vérifier la disponibilité."
                        ),
                    }
                }

            _logger_booking.info(
                "🔍 Appel moteur disponibilité | type=%s | in=%s | out=%s | stay=%s",
                rec.room_type_id.name,
                rec.planned_checkin_date,
                rec.planned_checkout_date,
                rec.id,
            )
            availability_engine = self.env["hotel.room.availability.engine"]
            availability_result = availability_engine.check_availability(
                room_type_id=rec.room_type_id.id,
                checkin_date=rec.planned_checkin_date,
                checkout_date=rec.planned_checkout_date,
                exclude_stay_id=rec.id if rec.id else None,
                buffer_hours=buffer_hours,
                reservation_type_id=(
                    rec.reservation_type_id.id if rec.reservation_type_id else None
                ),
            )

            _logger_booking.info(
                "📊 [ONCHANGE] Résultat disponibilité | status=%s | room=%s",
                availability_result.get("status"),
                availability_result.get("room_name", "N/A"),
            )

            # === CAS 1 : DISPONIBLE ===
            if availability_result["status"] == "available":
                if availability_result.get("room_id"):
                    # Attribution automatique si pas déjà assignée
                    if not rec.room_id:
                        rec.room_id = availability_result["room_id"]
                        _logger_booking.info(
                            "✅ Chambre assignée automatiquement | room=%s",
                            availability_result.get("room_name"),
                        )
                        return {
                            "warning": {
                                "title": _("✅ Chambre disponible"),
                                "message": _(
                                    'La chambre "%s" a été assignée automatiquement.'
                                )
                                % availability_result.get("room_name"),
                            }
                        }
                return None  # Pas de warning si déjà assignée

            # === CAS 2 : INDISPONIBLE ===
            elif availability_result["status"] == "unavailable":
                alternatives = availability_result.get("alternatives", [])
                reason = availability_result.get("reason", "unavailable")

                # Construction du message d'erreur
                if reason == "no_rooms":
                    warning_msg = (
                        _("❌ Aucune chambre de type '%s' n'existe dans le système.")
                        % rec.room_type_id.name
                    )
                else:
                    warning_msg = availability_result.get(
                        "message", _("Aucune chambre disponible pour ces dates.")
                    )

                # Ajouter les alternatives
                if alternatives:
                    warning_msg += "\n\n" + _("📋 Créneaux alternatifs disponibles :")
                    for idx, alt in enumerate(alternatives[:3], 1):
                        alt_in = alt["checkin"].strftime("%d/%m/%Y %H:%M")
                        alt_out = alt["checkout"].strftime("%d/%m/%Y %H:%M")
                        warning_msg += f"\n  {idx}. Chambre {alt['room_name']}: {alt_in} → {alt_out}"

                    warning_msg += "\n\n⚠️ L'enregistrement sera BLOQUÉ si vous continuez avec ces dates."
                else:
                    warning_msg += "\n\n⚠️ Aucune alternative disponible. Veuillez choisir d'autres dates ou un autre type de chambre."

                # Afficher les détails de conflit en mode debug
                # conflicts = availability_result.get('conflict_details', [])
                # if conflicts and _logger_booking.isEnabledFor(logging.DEBUG):
                # warning_msg += f"\n\n[DEBUG] {len(conflicts)} conflit(s) détecté(s) :"
                # for conf in conflicts[:3]:
                # warning_msg += f"\n  - Chambre {conf.get('room_name')}: {conf.get('overlap_type')}"

                _logger_booking.warning("⚠️ [ONCHANGE] Indisponible | reason=%s", reason)

                return {
                    "warning": {
                        "title": _("❌ Aucune chambre disponible"),
                        "message": warning_msg,
                    }
                }

            # === CAS 3 : ERREUR ===
            elif availability_result["status"] == "error":
                error_msg = availability_result.get(
                    "message", _("Erreur lors de la vérification")
                )
                _logger_booking.error("[ONCHANGE] Erreur moteur | msg=%s", error_msg)

                return {
                    "warning": {
                        "title": _("⚠️ Erreur"),
                        "message": _(
                            "Erreur lors de la vérification de disponibilité :\n%s\n\n"
                            "L'enregistrement pourrait être bloqué."
                        )
                        % error_msg,
                    }
                }

        except Exception as e:
            _logger_booking.exception(
                "🔥 [ONCHANGE] Exception | stay=%s | err=%s", rec.id or "new", str(e)
            )
            return {
                "warning": {
                    "title": _("⚠️ Erreur technique"),
                    "message": _(
                        "Impossible de vérifier la disponibilité.\n"
                        "Détails : %s\n\n"
                        "L'enregistrement pourrait être bloqué."
                    )
                    % str(e),
                }
            }

    @api.constrains(
        "room_type_id",
        "booking_start_date",
        "booking_end_date",
        "reservation_type_id",
        "planned_checkin_date",
        "planned_checkout_date",
    )
    def _check_room_availability(self):
        """
        Contrainte bloquante : empêche l'enregistrement si aucune chambre n'est disponible.
        """
        for rec in self:
            _logger_booking.debug(
                "🔒 _check_room_availability déclenché pour stay %s", rec.id
            )

            if not rec.planned_checkin_date or not rec.planned_checkout_date:
                _logger_booking.info(
                    "📆 Forçage du calcul planned dates pour stay %s", rec.id
                )
                rec._compute_dates_logic(rec)
                if not rec.planned_checkin_date:
                    _logger_booking.warning(
                        "⚠️ Impossible de calculer les dates planned pour stay %s",
                        rec.id,
                    )
                    continue

            if not rec.room_type_id:
                _logger_booking.debug(
                    "⚠️ Pas de room_type_id, contrainte ignorée pour stay %s", rec.id
                )
                continue

            _logger_booking.info(
                "🔒 Vérification contrainte disponibilité | type=%s | in=%s | out=%s",
                rec.room_type_id.name,
                rec.planned_checkin_date,
                rec.planned_checkout_date,
            )

            try:
                availability_engine = self.env["hotel.room.availability.engine"]
                availability_result = availability_engine.check_availability(
                    room_type_id=rec.room_type_id.id,
                    checkin_date=rec.planned_checkin_date,
                    checkout_date=rec.planned_checkout_date,
                    exclude_stay_id=rec.id if rec.id else None,
                    buffer_hours=0.5,
                    reservation_type_id=(
                        rec.reservation_type_id.id if rec.reservation_type_id else None
                    ),
                )

                status = availability_result.get("status")
                _logger_booking.info(
                    "[CONSTRAINT] Résultat moteur | status=%s | room=%s",
                    status,
                    availability_result.get("room_name", "N/A"),
                )

                if status == "unavailable":
                    _logger_booking.error(
                        "[CONSTRAINT] BLOCAGE | aucune chambre disponible."
                    )
                    raise ValidationError(
                        availability_result.get(
                            "message", "Aucune chambre disponible pour ces dates."
                        )
                    )

                elif status == "error":
                    _logger_booking.error(
                        "[CONSTRAINT] Erreur moteur : %s",
                        availability_result.get("message"),
                    )
                    raise ValidationError(
                        _("Erreur technique : %s") % availability_result.get("message")
                    )

                elif (
                    status == "available"
                    and availability_result.get("room_id")
                    and not rec.room_id
                ):
                    rec.room_id = availability_result["room_id"]
                    _logger_booking.info(
                        "✅ [CONSTRAINT] Chambre assignée automatiquement | room=%s",
                        availability_result.get("room_name"),
                    )

            except ValidationError:
                raise
            except Exception as e:
                _logger_booking.exception(
                    "🔥 Exception contrainte stay=%s | err=%s", rec.id, str(e)
                )
                raise ValidationError(
                    _("Erreur critique de disponibilité : %s") % str(e)
                )

    # Alerte non bloquante (prévenir utilisateur)
    @api.onchange("planned_checkin_date", "planned_checkout_date")
    def _onchange_extra_night(self):
        for rec in self:
            if rec.extra_night_required:
                _logger_booking.warning(
                    "⚠️ Alerte extra night déclenchée pour stay %s", rec.id
                )
                return {
                    "warning": {
                        "title": _("Attention : Nuit Supplémentaire"),
                        "message": _(
                            "L'horaire demandé sort des limites standards. "
                            "Une nuit supplémentaire sera peut-être requise."
                        ),
                    }
                }

    @api.constrains("booking_start_date", "booking_end_date", "reservation_type_id")
    def _check_booking_dates_order(self):
        for rec in self:
            if (
                rec.reservation_type_id
                and rec.reservation_type_id.code == "classic"
                and rec.booking_start_date
                and rec.booking_end_date
                and rec.booking_end_date < rec.booking_start_date
            ):
                raise ValidationError(
                    _(
                        "La date de fin de réservation ne peut pas être antérieure à la date de début."
                    )
                )

    # Vérification bloquante (empêche enregistrement incohérent)
    @api.constrains("planned_checkin_date", "planned_checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if (
                rec.planned_checkin_date
                and rec.planned_checkout_date
                and rec.planned_checkout_date < rec.planned_checkin_date
            ):
                raise ValidationError(
                    _("La date de départ ne peut pas être avant la date d'arrivée.")
                )

    # Onchange = confort utilisateur ajutstement de date
    @api.onchange("planned_checkin_date", "planned_checkout_date")
    def _onchange_checkin_date(self):
        if (
            self.planned_checkin_date
            and self.planned_checkout_date
            and self.planned_checkout_date < self.planned_checkin_date
        ):
            self.planned_checkout_date = self.planned_checkin_date + timedelta(days=1)
            return {
                "warning": {
                    "title": _("Correction automatique"),
                    "message": _(
                        "La date de départ a été ajustée car elle était avant la date d'arrivée."
                    ),
                }
            }

    # =========================Gestion EC/LC=========================#
    @api.onchange("early_checkin_requested", "late_checkout_requested")
    def _onchange_eclc_requested(self):
        """
        Synchronise les cases à cocher avec le pricing.
        Si les deux sont cochées, on calcule les deux séparément.
        """
        for rec in self:
            _logger.info(
                "[ONCHANGE] early=%s, late=%s",
                rec.early_checkin_requested,
                rec.late_checkout_requested,
            )

            # Si aucune demande → reset complet
            if not rec.early_checkin_requested and not rec.late_checkout_requested:
                _logger.info("[ONCHANGE] Reset complet pour stay %s", rec.id)
                rec.request_type = False
                rec.early_checkin_price = 0.0
                rec.late_checkout_price = 0.0
                rec.room_price_total = 0.0
                rec.pricing_rule_id = False
                rec.pricing_adjustments = False
                rec.pricing_price_base = 0.0
                continue

            # Si un seul des deux cochés → simple recalcul
            if rec.early_checkin_requested and not rec.late_checkout_requested:
                rec.request_type = "early"
                _logger.info("[ONCHANGE] Stay %s → recalcul EARLY uniquement", rec.id)
                rec._compute_room_price_total()
                continue

            if rec.late_checkout_requested and not rec.early_checkin_requested:
                rec.request_type = "late"
                _logger.info("[ONCHANGE] Stay %s → recalcul LATE uniquement", rec.id)
                rec._compute_room_price_total()
                continue

            # Si les deux cochés → recalcul double
            if rec.early_checkin_requested and rec.late_checkout_requested:
                _logger.info("[ONCHANGE] Stay %s → recalcul EARLY + LATE", rec.id)

                # Calcul séparé Early
                rec.request_type = "early"
                rec._compute_room_price_total()
                early_price = rec.early_checkin_price
                _logger.info("→ Early Price calculé = %s", early_price)

                # Calcul séparé Late
                rec.request_type = "late"
                rec._compute_room_price_total()
                late_price = rec.late_checkout_price
                _logger.info("→ Late Price calculé = %s", late_price)

                # On additionne les deux
                rec.room_price_total = rec.pricing_price_base + early_price + late_price
                _logger.info(
                    "[ONCHANGE] Stay %s → total=%s (base=%s + early=%s + late=%s)",
                    rec.id,
                    rec.room_price_total,
                    rec.pricing_price_base,
                    early_price,
                    late_price,
                )

                # Remise à zéro du request_type pour éviter d'écraser les horaires
                rec.request_type = False

    ### calcul du type de demande (early/late)
    @api.depends("early_checkin_requested", "late_checkout_requested")
    def _compute_request_type(self):
        for rec in self:
            if rec.early_checkin_requested and not rec.late_checkout_requested:
                rec.request_type = "early"
            elif rec.late_checkout_requested and not rec.early_checkin_requested:
                rec.request_type = "late"
            else:
                rec.request_type = False

    @api.depends(
        "planned_checkin_date",
        "planned_checkout_date",
        "requested_checkin_datetime",
        "requested_checkout_datetime",
        "early_checkin_requested",
        "late_checkout_requested",
    )
    def _compute_actual_checkin_checkout(self):
        for rec in self:
            early_late_logger.info(
                "[COMPUTE] stay=%s planned_in=%s planned_out=%s early_req=%s late_req=%s",
                rec.id,
                rec.planned_checkin_date,
                rec.planned_checkout_date,
                rec.early_checkin_requested,
                rec.late_checkout_requested,
            )

            rec.actual_checkin_date = rec.planned_checkin_date
            rec.actual_checkout_date = rec.planned_checkout_date
            rec.early_pricing_mode = False
            rec.late_pricing_mode = False
            rec.extra_night_required = False
            rec.availability_status = "unknown"
            rec.availability_message = ""

            # --- Early ---
            if rec.early_checkin_requested and rec.requested_checkin_datetime:
                early_late_logger.info(
                    "[EARLY] Checking request stay=%s requested=%s",
                    rec.id,
                    rec.requested_checkin_datetime,
                )
                verdict = rec._evaluate_stay_request(
                    rec,
                    request_type="early",
                    requested_datetime=rec.requested_checkin_datetime,
                    planned_datetime=rec.planned_checkin_date,
                )
                early_late_logger.info("[EARLY VERDICT] %s", verdict)

                rec.early_pricing_mode = verdict.get("pricing_mode") or False
                if verdict["status"] in ("accepted", "extra_night"):
                    rec.actual_checkin_date = verdict["actual_in"]
                    rec.actual_checkout_date = verdict["actual_out"]
                    rec.extra_night_required = verdict["status"] == "extra_night"

                rec.availability_status = verdict.get("availability_status", "unknown")
                rec.availability_message = verdict.get("message", "")

            # --- Late ---
            if rec.late_checkout_requested and rec.requested_checkout_datetime:
                early_late_logger.info(
                    "[LATE] Checking request stay=%s requested=%s",
                    rec.id,
                    rec.requested_checkout_datetime,
                )
                verdict = rec._evaluate_stay_request(
                    rec,
                    request_type="late",
                    requested_datetime=rec.requested_checkout_datetime,
                    planned_datetime=rec.planned_checkout_date,
                )
                early_late_logger.info("[LATE VERDICT] %s", verdict)

                rec.late_pricing_mode = verdict.get("pricing_mode") or False
                if verdict["status"] in ("accepted", "extra_night"):
                    rec.actual_checkin_date = verdict["actual_in"]
                    rec.actual_checkout_date = verdict["actual_out"]
                    rec.extra_night_required = verdict["status"] == "extra_night"

                rec.availability_status = verdict.get("availability_status", "unknown")
                rec.availability_message = verdict.get("message", "")

            early_late_logger.info(
                "[FINAL] stay=%s actual_in=%s actual_out=%s early_mode=%s late_mode=%s extra_night=%s avail=%s msg=%s",
                rec.id,
                rec.actual_checkin_date,
                rec.actual_checkout_date,
                rec.early_pricing_mode,
                rec.late_pricing_mode,
                rec.extra_night_required,
                rec.availability_status,
                rec.availability_message,
            )

    # -----------------Fonction utilitaire combinée------------------#
    def _evaluate_stay_request(
        self, rec, request_type, requested_datetime, planned_datetime
    ):
        early_late_logger.info(
            "[EVAL] stay=%s type=%s requested=%s planned=%s",
            rec.id,
            request_type,
            requested_datetime,
            planned_datetime,
        )

        engine_eclc = self.env["hotel.eclc.engine"]
        engine_avail = self.env["hotel.availability.engine"]

        # --- Étape 1 : ECLC ---
        result_eclc = engine_eclc.evaluate_request(
            request_type=request_type,
            requested_datetime=requested_datetime,
            planned_datetime=planned_datetime,
            room_type_id=rec.room_type_id.id,
        )
        early_late_logger.info("[EVAL][ECLC] %s", result_eclc)

        status_eclc = result_eclc.get("status")
        pricing_mode = result_eclc.get("pricing_mode")

        if status_eclc == "refused":
            early_late_logger.warning("[EVAL] Refusé par ECLC stay=%s", rec.id)
            return {
                "status": "refused",
                "actual_in": rec.planned_checkin_date,
                "actual_out": rec.planned_checkout_date,
                "pricing_mode": False,
                "availability_status": "not_checked",
                "message": "❌ Refusé par ECLC",
            }

        # --- Étape 2 : Dates proposées ---
        proposed_in = rec.planned_checkin_date
        proposed_out = rec.planned_checkout_date
        if request_type == "early" and status_eclc == "accepted":
            proposed_in = requested_datetime
        elif request_type == "late" and status_eclc == "accepted":
            proposed_out = requested_datetime
        elif status_eclc == "extra_night":
            from datetime import timedelta

            proposed_out = (
                requested_datetime
                if request_type == "late"
                else rec.planned_checkout_date + timedelta(days=1)
            )

        early_late_logger.info(
            "[EVAL] stay=%s proposed_in=%s proposed_out=%s",
            rec.id,
            proposed_in,
            proposed_out,
        )

        # --- Étape 3 : Disponibilité ---
        result_avail = engine_avail.check_availability(
            room_type_id=rec.room_type_id.id,
            start=proposed_in,
            end=proposed_out,
        )
        early_late_logger.info("[EVAL][AVAIL] %s", result_avail)

        if result_avail["status"] == "available":
            verdict = {
                "status": status_eclc,
                "actual_in": proposed_in,
                "actual_out": proposed_out,
                "pricing_mode": pricing_mode,
                "availability_status": "available",
                "message": f"✅ {status_eclc} + dispo : {result_avail['message']}",
            }
        else:
            verdict = {
                "status": "refused",
                "actual_in": rec.planned_checkin_date,
                "actual_out": rec.planned_checkout_date,
                "pricing_mode": False,
                "availability_status": "unavailable",
                "message": f"❌ {status_eclc} mais indispo : {result_avail['message']}",
            }

        early_late_logger.info("[EVAL][FINAL] stay=%s verdict=%s", rec.id, verdict)
        return verdict

    ###############################################
    # Gestion des tarifications
    ###############################################
    @api.depends(
        "room_type_id",
        "reservation_type_id",
        "planned_checkin_date",
        "planned_checkout_date",
        "occupant_ids",
        "early_checkin_requested",
        "late_checkout_requested",
        "early_pricing_mode",
        "late_pricing_mode",
        "requested_checkin_datetime",
        "requested_checkout_datetime",
    )
    def _compute_room_price_total(self):
        """
        Calcule le prix de la  chambre en appelant le service tarifaire.
        Gère les suppléments Early Check-in / Late Check-out en parallèle.
        """
        for rec in self:
            # Reset par défaut
            rec.room_price_total = 0.0
            rec.pricing_rule_id = False
            rec.pricing_unit = False
            rec.pricing_unit_price = 0.0
            rec.pricing_quantity = 0.0
            rec.pricing_adjustments = False
            rec.pricing_price_base = 0.0
            rec.pricing_supplements = False
            rec.early_checkin_fee = 0.0
            rec.late_checkout_fee = 0.0

            ctx = {
                "stay_id": rec.id or None,
                "booking_id": rec.booking_id.id if rec.booking_id else None,
                "room_type_id": rec.room_type_id.id if rec.room_type_id else None,
                "reservation_type_id": (
                    rec.reservation_type_id.id if rec.reservation_type_id else None
                ),
                "planned_checkin_date": rec.planned_checkin_date
                and rec.planned_checkin_date.isoformat(),
                "planned_checkout_date": rec.planned_checkout_date
                and rec.planned_checkout_date.isoformat(),
                "nb_persons": len(rec.occupant_ids) or 1,
                "user_tz": self.env.user.tz,
            }

            _logger_booking.info(
                "📌 [STAY/INIT] Début calcul prix chambre | ctx=%s", ctx
            )

            if not (
                rec.room_type_id
                and rec.reservation_type_id
                and rec.planned_checkin_date
                and rec.planned_checkout_date
            ):
                _logger_booking.debug(
                    "[PRICING][SKIP] Inputs incomplets pour stay=%s | ctx=%s",
                    rec.id or "new",
                    json.dumps(ctx, ensure_ascii=False),
                    ctx,
                )
                continue

            # =========================================================
            # 1) Collecter les modes ECLC et datetimes associés
            # =========================================================
            pricing_modes = []
            requested_map = {}

            if rec.early_pricing_mode:
                pricing_modes.append(rec.early_pricing_mode)
                if rec.requested_checkin_datetime:
                    requested_map["early_fee"] = rec.requested_checkin_datetime

            if rec.late_pricing_mode:
                pricing_modes.append(rec.late_pricing_mode)
                if rec.requested_checkout_datetime:
                    requested_map["late_fee"] = rec.requested_checkout_datetime

            _logger.info(
                "[PRICING][INPUT] stay=%s | modes=%s | requested_map=%s",
                rec.id or "new",
                pricing_modes,
                {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in requested_map.items()
                },
            )

            # =========================================================
            # 2) Appel au moteur tarifaire
            # =========================================================
            try:
                _logger_booking.info(
                    "➡️ [STAY/CALL] Appel moteur tarifaire pour stay=%s", rec.id
                )
                result = self.env["hotel.pricing.service"].compute_price(
                    room_type_id=rec.room_type_id.id,
                    reservation_type_id=rec.reservation_type_id.id,
                    planned_checkin_date=rec.planned_checkin_date,
                    planned_checkout_date=rec.planned_checkout_date,
                    nb_persons=len(rec.occupant_ids) or 1,
                    pricing_mode=pricing_modes,
                    requested_datetime=requested_map,
                )

                _logger_booking.info(
                    "[PRICING][RAW] stay=%s | result=%s",
                    rec.id or "new",
                    json.dumps(result, ensure_ascii=False, indent=2, default=str),
                )

                if not isinstance(result, dict):
                    _logger.error(
                        "[PRICING][ERR] Résultat non dict pour stay=%s | result=%s",
                        rec.id,
                        result,
                    )
                    continue

                # =========================================================
                # 3) Affecter les résultats
                # =========================================================
                base_data = result.get("base", {})
                rec.pricing_price_base = float(base_data.get("amount", 0.0))
                rec.room_price_total = float(result.get("total", 0.0))
                rec.pricing_rule_id = base_data.get("rule_id") or False
                rec.pricing_unit = base_data.get("unit") or False
                rec.pricing_unit_price = float(base_data.get("unit_price", 0.0))
                rec.pricing_quantity = float(base_data.get("quantity", 0.0))
                rec.pricing_adjustments = json.dumps(
                    result.get("adjustments", []), ensure_ascii=False, indent=2
                )
                rec.pricing_supplements = json.dumps(
                    result.get("supplements", []), ensure_ascii=False, indent=2
                )

                # Extraire les suppléments Early/Late
                for sup in result.get("supplements", []):
                    if sup.get("type") == "early_checkin":
                        rec.early_checkin_fee = float(sup.get("amount", 0.0))
                        early_late_logger.info(
                            "[COMPUTE][EC] stay=%s | montant=%s | details=%s",
                            rec.id,
                            rec.early_checkin_fee,
                            sup,
                        )
                    elif sup.get("type") == "late_checkout":
                        rec.late_checkout_fee = float(sup.get("amount", 0.0))
                        early_late_logger.info(
                            "[COMPUTE][LC] stay=%s | montant=%s | details=%s",
                            rec.id,
                            rec.late_checkout_fee,
                            sup,
                        )

                rec.financial_summary_details = json.dumps(
                    result, ensure_ascii=False, indent=2, default=str
                )

                _logger.info(
                    "[CHECK FINANCIAL] stay=%s | financial_summary_details=%s",
                    rec.id,
                    rec.financial_summary_details,
                )
                early_late_logger.info(
                    "[PRICING][OK] stay=%s | base=%s | total=%s | rule_id=%s | adjustments=%s | supplements=%s,| summary=%s",
                    rec.id,
                    rec.pricing_price_base,
                    rec.room_price_total,
                    rec.pricing_rule_id,
                    rec.pricing_unit,
                    rec.pricing_unit_price,
                    rec.pricing_quantity,
                    rec.pricing_adjustments,
                    rec.pricing_supplements,
                    rec.financial_summary_details,
                    rec.early_checkin_fee,
                    rec.late_checkout_fee,
                )
                _logger_booking.info(
                    "✅ [STAY/OK] stay=%s | base=%s | total=%s | rule_id=%s | unit=%s | qty=%s",
                    rec.id,
                    rec.pricing_price_base,
                    rec.room_price_total,
                    rec.pricing_rule_id,
                    rec.pricing_unit,
                    rec.pricing_quantity,
                )

            except Exception as e:
                _logger.exception(
                    "[PRICING][EXC] Erreur compute_price pour stay=%s | ctx=%s | err=%s",
                    rec.id,
                    json.dumps(ctx, ensure_ascii=False),
                    e,
                )
                _logger_booking.exception(
                    "🔥 [STAY/EXC] Erreur compute_price pour stay=%s | ctx=%s | err=%s",
                    rec.id,
                    ctx,
                    e,
                )

    def _prepare_invoice_line(self):
        """Prépare les valeurs d'une ligne de facture à partir du séjour"""
        self.ensure_one()

        if not self.product_id:
            raise UserError(
                _("Aucun produit défini pour ce séjour (stay %s)") % self.display_name
            )

        return {
            "product_id": self.product_id.id,
            "name": "%s (%s → %s)"
            % (
                self.product_id.display_name,
                self.planned_checkin_date.strftime("%d/%m/%Y"),
                self.planned_checkout_date.strftime("%d/%m/%Y"),
            ),
            "quantity": 1,  # tu peux remplacer par rec.pricing_quantity si besoin
            "price_unit": self.pricing_price_base,  # prix calculé total
            "tax_ids": [(6, 0, self.product_id.taxes_id.ids)],
            "currency_id": self.currency_id.id,
        }

    def _prepare_invoice_line_for_fee(self, product, amount, label):
        """Prépare une ligne pour un supplément (early/late)"""
        return {
            "product_id": product.id,
            "name": "%s - %s" % (product.display_name, label),
            "quantity": 1,
            "price_unit": amount,
            "tax_ids": [(6, 0, product.taxes_id.ids)],
            "currency_id": self.currency_id.id,
        }

    def action_create_invoice(self):
        """Crée la facture pour ce séjour"""
        for stay in self:
            if not stay.booking_id:
                raise UserError(_("Impossible de facturer un séjour sans réservation"))

            # 1) Chercher ou créer une facture brouillon
            move = self.env["account.move"].search(
                [
                    ("stay_id", "=", self.id),
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "draft"),
                ],
                limit=1,
            )
            if not move:
                move = self.env["account.move"].create(
                    {
                        "move_type": "out_invoice",
                        "partner_id": stay.booking_id.partner_id.id,
                        "stay_id": self.id,
                        "currency_id": stay.currency_id.id,
                    }
                )

            # 2) Ajouter la ligne de facture
            self.env["account.move.line"].create(
                dict(stay._prepare_invoice_line(), move_id=move.id)
            )

            # Supplément Early Checkin
            if stay.early_checkin_fee > 0:
                # product_early = self.env["product.product"].search([
                #   ("product_tmpl_id.name", "=", "Early Checkin Chambre A")], limit=1
                # )
                product_early = self.env["product.product"].search(
                    [("product_tmpl_id.name", "ilike", "Early Checkin Chambre A")],
                    limit=1,
                )
                if not product_early:
                    raise UserError(_("Produit 'Early Checkin' introuvable"))

                self.env["account.move.line"].create(
                    dict(
                        stay._prepare_invoice_line_for_fee(
                            product_early,
                            stay.early_checkin_fee,
                            "Early Checkin Chambre A",
                        ),
                        move_id=move.id,
                    )
                )
                early_late_logger.info(
                    "[INVOICE][EC] stay=%s | invoice_id=%s | produit=%s | montant=%s",
                    stay.id,
                    move.id,
                    product_early.display_name,
                    stay.early_checkin_fee,
                )

            # Supplément Late Checkout
            if stay.late_checkout_fee > 0:
                # product_late = self.env["product.product"].search([
                #   ("product_tmpl_id.name", "=", "Late Checkout Chambre A")
                # ], limit=1)

                product_late = self.env["product.product"].search(
                    [("product_tmpl_id.name", "ilike", "Late Checkout Chambre A")],
                    limit=1,
                )

                if not product_late:
                    raise UserError(_("Produit 'Late Checkout' introuvable"))

                self.env["account.move.line"].create(
                    dict(
                        stay._prepare_invoice_line_for_fee(
                            product_late,
                            stay.late_checkout_fee,
                            "Late Checkout Chambre A",
                        ),
                        move_id=move.id,
                    )
                )
                early_late_logger.info(
                    "[INVOICE][LC] stay=%s | invoice_id=%s | produit=%s | montant=%s",
                    stay.id,
                    move.id,
                    product_late.display_name,
                    stay.late_checkout_fee,
                )

            # Récupérer les factures POS liées
            pos_invoices = self.env["account.move"].search(
                [
                    ("stay_id", "=", stay.id),
                    ("to_invoice_with_stay", "=", True),
                    ("state", "in", ["draft", "posted"]),
                ]
            )
            _logger.info(
                "[INVOICE][POS] %d factures POS liées trouvées pour stay=%s",
                len(pos_invoices),
                stay.id,
            )

            for pos_move in pos_invoices:
                for line in pos_move.invoice_line_ids:
                    # Créer une nouvelle ligne sur la facture séjour
                    vals = {
                        "move_id": move.id,
                        "product_id": line.product_id.id,
                        "name": f"{line.name} (Reprise POS {pos_move.name})",
                        "quantity": line.quantity,
                        "price_unit": line.price_unit,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
                        "currency_id": move.currency_id.id,
                    }
                    self.env["account.move.line"].create(vals)
                    _logger.info(
                        "[INVOICE][POS-LINE] Reprise %s (qte=%s, prix=%s) depuis facture POS %s → facture séjour %s",
                        line.product_id.display_name,
                        line.quantity,
                        line.price_unit,
                        pos_move.name,
                        move.name,
                    )

                # Marquer la facture POS comme reportée
                pos_move.message_post(
                    body=f"Facture POS reportée sur la facture séjour {move.name}"
                )
                pos_move.write(
                    {
                        "to_invoice_with_stay": False,
                        "pos_invoice_reported": True,
                    }
                )
                _logger.info(
                    "[INVOICE][POS-LINKED] Facture POS %s marquée comme reportée",
                    pos_move.name,
                )

            # Log final
            _logger.info(
                "[INVOICE][DONE] Facture séjour %s générée avec %d lignes POS intégrées",
                move.name,
                len(pos_invoices),
            )

        return True

    def action_create_and_open_invoice(self):
        """Crée la facture et ouvre la vue de la facture"""
        self.ensure_one()

        # Appeler la méthode existante pour créer la facture
        self.action_create_invoice()

        # Récupérer la facture créée ou existante
        move = self.env["account.move"].search(
            [
                ("stay_id", "=", self.id),
                ("move_type", "=", "out_invoice"),
            ],
            order="id desc",
            limit=1,
        )

        if not move:
            raise UserError(_("Aucune facture trouvée pour ce séjour."))

        # Retourner une action pour ouvrir la vue facture
        return {
            "type": "ir.actions.act_window",
            "name": _("Facture du séjour"),
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_invoice(self):
        self.ensure_one()
        invoice = self.env["account.move"].search(
            [("stay_id", "=", self.id), ("move_type", "=", "out_invoice")],
            limit=1,
        )
        if not invoice:
            raise UserError(_("Aucune facture n'est associée à ce séjour."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": invoice.id,
            "target": "current",
        }

    # -----------  -------------

    def get_financial_summary(self):
        """
        Retourne un tableau exploitable pour l'impression (facture, récapitulatif, etc.)
        """
        self.ensure_one()
        if not self.financial_summary_details:
            return []

        summary = json.loads(self.financial_summary_details)

        lines = []

        # Prix de base
        if summary.get("base"):
            base = summary["base"]
            lines.append(
                {
                    "label": f"Chambre ({base.get('quantity')} x {base.get('unit')})",
                    "amount": base.get("amount", 0.0),
                }
            )

        # Ajustements
        for adj in summary.get("adjustments", []):
            lines.append(
                {
                    "label": adj.get("label", "Ajustement"),
                    "amount": adj.get("amount", 0.0),
                }
            )

        # Suppléments
        for sup in summary.get("supplements", []):
            lines.append(
                {
                    "label": sup.get("label", "Supplément"),
                    "amount": sup.get("amount", 0.0),
                }
            )

        # Remises
        for disc in summary.get("discounts", []):
            lines.append(
                {
                    "label": disc.get("label", "Remise"),
                    "amount": -disc.get("amount", 0.0),
                }
            )

        # Total
        lines.append(
            {
                "label": "TOTAL",
                "amount": summary.get("total", 0.0),
            }
        )

        _logger.info(
            "[REPORT] stay=%s | financial_summary_details=%s",
            self.id,
            self.financial_summary_details,
        )

        return lines

    # ---------- Gestion des EC LC ----------

    # ==================== OPTIMISATION SUPPLÉMENTAIRE ====================
    # Ajouter une méthode de validation avant create/write

    def _validate_availability_before_save(self):
        """
        Validation explicite avant sauvegarde.
        Peut être appelée manuellement ou dans un workflow.
        """
        for rec in self:
            if rec.is_flexible_reservation:
                continue

            if not rec.planned_checkin_date or not rec.planned_checkout_date:
                if (
                    rec.booking_start_date
                    and rec.booking_end_date
                    and rec.reservation_type_id
                ):
                    rec._compute_dates_logic(rec)

            if (
                not rec.room_type_id
                or not rec.planned_checkin_date
                or not rec.planned_checkout_date
            ):
                continue

            # Même logique que la contrainte
            availability_engine = self.env["hotel.room.availability.engine"]
            result = availability_engine.check_availability(
                room_type_id=rec.room_type_id.id,
                checkin_date=rec.planned_checkin_date,
                checkout_date=rec.planned_checkout_date,
                exclude_stay_id=rec.id if rec.id else None,
                buffer_hours=0.5,
                reservation_type_id=(
                    rec.reservation_type_id.id if rec.reservation_type_id else None
                ),
            )

            if result["status"] == "unavailable":
                raise ValidationError(
                    result.get("message", "Aucune chambre disponible")
                )

    @api.model
    def create(self, vals):
        """S'assurer que actual = planned par défaut + validation disponibilité"""
        if not vals.get("actual_checkin_date") and vals.get("planned_checkin_date"):
            vals["actual_checkin_date"] = vals["planned_checkin_date"]
        if not vals.get("actual_checkout_date") and vals.get("planned_checkout_date"):
            vals["actual_checkout_date"] = vals["planned_checkout_date"]

        record = super().create(vals)
        try:
            record._validate_availability_before_save()
        except ValidationError as e:
            # Si validation échoue, supprimer l'enregistrement créé
            record.unlink()
            raise e

        return record

    def write(self, vals):
        """Si les dates prévues changent, on ajuste les actuals (sauf si déjà modifiées par EC/LC)"""
        for rec in self:
            if "planned_checkin_date" in vals and not rec.request_type:
                vals.setdefault("actual_checkin_date", vals["planned_checkin_date"])
            if "planned_checkout_date" in vals and not rec.request_type:
                vals.setdefault("actual_checkout_date", vals["planned_checkout_date"])
        return super().write(vals)

    @api.depends(
        "requested_checkin_datetime",
        "requested_checkout_datetime",
        "planned_checkin_date",
        "planned_checkout_date",
    )
    def _compute_difference_hours(self):
        for rec in self:
            rec.early_difference_hours = 0.0
            rec.late_difference_hours = 0.0

            if (
                rec.early_checkin_requested
                and rec.requested_checkin_datetime
                and rec.planned_checkin_date
            ):
                diff = (
                    rec.planned_checkin_date - rec.requested_checkin_datetime
                ).total_seconds() / 3600.0
                rec.early_difference_hours = max(diff, 0.0)
                _logger.info(
                    "[DIFF EARLY] stay=%s diff=%.2fH",
                    rec.id,
                    rec.early_difference_hours,
                )

            if (
                rec.late_checkout_requested
                and rec.requested_checkout_datetime
                and rec.planned_checkout_date
            ):
                diff = (
                    rec.requested_checkout_datetime - rec.planned_checkout_date
                ).total_seconds() / 3600.0
                rec.late_difference_hours = max(diff, 0.0)
                _logger.info(
                    "[DIFF LATE] stay=%s diff=%.2fH", rec.id, rec.late_difference_hours
                )

    # Invoice

    def action_preview_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.report",
            "report_name": "hotel_management_extension.report_hotel_stay_invoice",  # ✅ correction
            "report_type": "qweb-html",
            "data": {"ids": [self.id]},
            "context": {
                "active_ids": [self.id],
                "active_model": "hotel.booking.stay",
            },
        }

    def action_print_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.report",
            "report_name": "hotel_management_extension.report_hotel_stay_invoice",  # ✅ correction
            "report_type": "qweb-pdf",
            "data": {"ids": [self.id]},
            "context": {
                "active_ids": [self.id],
                "active_model": "hotel.booking.stay",
            },
        }

    @api.model
    def create_stay_from_ui(self, values):
        """
        Test basique de création depuis OWL
        """
        # Vérif minimum
        if not values.get("room_type_id") or not values.get("booking_id"):
            raise ValidationError(
                _("Il faut au moins un booking et un type de chambre.")
            )

        # Création du séjour
        stay = self.create(values)

        # Retourner un payload simple pour OWL
        return {
            "id": stay.id,
            "booking_id": stay.booking_id.id if stay.booking_id else False,
            "room_type": stay.room_type_id.name if stay.room_type_id else None,
            "checkin": stay.planned_checkin_date,
            "checkout": stay.planned_checkout_date,
            "state": stay.state,
        }

    @api.model
    def add_stay_to_booking(self, vals):
        """
        Ajoute un séjour (stay) à une réservation existante via RPC.
        :param vals: dict contenant les champs nécessaires pour créer le stay
                     Exemple minimal :
                     {
                        "booking_id": 12,
                        "room_type_id": 5,
                        "reservation_type_id": 3,
                        "booking_start_date": "2025-08-30",
                        "booking_end_date": "2025-08-31",
                     }
        :return: dict {success: bool, message: str, data: dict}
        """
        try:
            # --- Vérification des champs obligatoires ---
            required_fields = [
                "booking_id",
                "room_type_id",
                "reservation_type_id",
                "booking_start_date",
                "booking_end_date",
            ]
            for field in required_fields:
                if field not in vals or not vals[field]:
                    raise ValidationError(_("Le champ '%s' est obligatoire.") % field)

            # --- Vérifier que la réservation existe ---
            booking = self.env["room.booking"].browse(vals["booking_id"])
            if not booking or not booking.exists():
                raise ValidationError(
                    _("La réservation (ID %s) est introuvable.") % vals["booking_id"]
                )

            # --- Vérifier que le type de chambre existe ---
            room_type = self.env["hotel.room.type"].browse(vals["room_type_id"])
            if not room_type or not room_type.exists():
                raise ValidationError(
                    _("Le type de chambre (ID %s) est introuvable.")
                    % vals["room_type_id"]
                )

            # --- Vérifier que le type de réservation existe ---
            resa_type = self.env["hotel.reservation.type"].browse(
                vals["reservation_type_id"]
            )
            if not resa_type or not resa_type.exists():
                raise ValidationError(
                    _("Le type de réservation (ID %s) est introuvable.")
                    % vals["reservation_type_id"]
                )

            # --- (Optionnel) Logique métier additionnelle ---
            # Exemple : interdire que la date de fin soit avant la date de début
            if vals["booking_end_date"] < vals["booking_start_date"]:
                raise ValidationError(
                    _(
                        "La date de fin de réservation ne peut pas être avant la date de début."
                    )
                )

            # --- Création du stay ---
            stay = self.create(vals)

            return {
                "success": True,
                "message": _("Séjour ajouté avec succès à la réservation."),
                "data": {
                    "stay_id": stay.id,
                    "booking_id": booking.id,
                    "state": stay.state,
                    "planned_checkin_date": stay.planned_checkin_date,
                    "planned_checkout_date": stay.planned_checkout_date,
                },
            }

        except (ValidationError, UserError) as e:
            return {
                "success": False,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
            }

    @api.model
    def compute_checkin_checkout(self, vals):
        """
        Calcule les dates de check-in et check-out pour un séjour,
        réutilise la logique interne `_compute_dates_logic`.

        :param vals: dict contenant les champs nécessaires :
            {
                "room_type_id": 5,
                "reservation_type_id": 3,
                "booking_start_date": "2025-08-30",
                "booking_end_date": "2025-08-31"
            }
        :return: dict {success: bool, message: str, data: dict}
        """
        try:
            # --- Vérification des champs obligatoires ---
            required_fields = [
                "room_type_id",
                "reservation_type_id",
                "booking_start_date",
                "booking_end_date",
            ]
            for field in required_fields:
                if field not in vals or not vals[field]:
                    raise ValidationError(_("Le champ '%s' est obligatoire.") % field)

            # --- Vérifier que le type de chambre existe ---
            room_type = self.env["hotel.room.type"].browse(vals["room_type_id"])
            if not room_type or not room_type.exists():
                raise ValidationError(
                    _("Le type de chambre (ID %s) est introuvable.")
                    % vals["room_type_id"]
                )

            # --- Vérifier que le type de réservation existe ---
            resa_type = self.env["hotel.reservation.type"].browse(
                vals["reservation_type_id"]
            )
            if not resa_type or not resa_type.exists():
                raise ValidationError(
                    _("Le type de réservation (ID %s) est introuvable.")
                    % vals["reservation_type_id"]
                )

            # --- Vérifier que les dates sont cohérentes ---
            start_date = fields.Date.from_string(vals["booking_start_date"])
            end_date = fields.Date.from_string(vals["booking_end_date"])
            if end_date < start_date:
                raise ValidationError(
                    _(
                        "La date de fin de réservation ne peut pas être avant la date de début."
                    )
                )

            # --- Création d'un record temporaire ---
            rec = self.new(
                {
                    "booking_start_date": start_date,
                    "booking_end_date": end_date,
                    "reservation_type_id": resa_type.id,
                    "room_type_id": room_type.id,
                }
            )

            # --- Appliquer la logique de calcul sur le record temporaire ---
            self._compute_dates_logic(rec)

            if not rec.planned_checkin_date or not rec.planned_checkout_date:
                return {
                    "success": False,
                    "message": _(
                        "Impossible de calculer les dates de séjour (slot manquant ou type flexible)."
                    ),
                    "data": {},
                }

            return {
                "success": True,
                "message": _("Dates calculées avec succès."),
                "data": {
                    "planned_checkin_date": rec.planned_checkin_date,
                    "planned_checkout_date": rec.planned_checkout_date,
                },
            }

        except (ValidationError, UserError) as e:
            return {
                "success": False,
                "message": str(e),
                "data": {},
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
                "data": {},
            }
