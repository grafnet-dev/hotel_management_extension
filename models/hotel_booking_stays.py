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

    # ouvrir un modal pour la fiche de police
    def action_start_checkin_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Fiche de Police",
            "res_model": "hotel.police.form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_stay_id": self.id,
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

    # OU si vous avez une relation avec hotel.police.form
    def action_preview_police_form(self):
        """Aperçu de la fiche de police pour ce séjour"""
        self.ensure_one()  # S'assurer qu'on travaille sur un seul séjour
        # Chercher s'il existe déjà une fiche de police pour ce séjour
        police_form = self.env["hotel.police.form"].search(
            [("stay_id", "=", self.id)], limit=1
        )

        if not police_form:
            # Lever un message d'erreur si aucune fiche n'existe
            raise UserError("Aucune fiche de police trouvée pour ce séjour.")

        # Ouvrir le rapport HTML pour l'aperçu
        return self.env.ref(
            "hotel_management_extension.action_report_hotel_police_form_html"
        ).report_action(police_form)

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

    # calcul automatique de la durée (methode à adapter plus tard)
    @api.depends("planned_checkin_date", "planned_checkout_date")
    def _compute_duration(self):
        for rec in self:
            if rec.planned_checkin_date and rec.planned_checkout_date:
                diff = rec.planned_checkout_date - rec.planned_checkin_date
                rec.uom_qty = diff.days + (1 if diff.total_seconds() > 0 else 0)
            else:
                rec.uom_qty = 0

    # Constraint = validation cohérence dates
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

    # Alerte non bloquante (prévenir utilisateur)
    @api.onchange("planned_checkin_date", "planned_checkout_date")
    def _onchange_extra_night(self):
        for rec in self:
            if rec.extra_night_required:
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

    # ----------- Calcul des dates en fonction du type de resa -------------

    def _compute_dates_logic(self, rec):
        """
        Logique partagée entre compute et onchange
        Recalcule automatiquement planned_checkin_date et planned_checkout_date 
        en fonction du type de réservation ET vérifie la disponibilité.
        """
        _logger_booking.debug("is_flexible_reservation=%s", rec.is_flexible_reservation)
        _logger_booking.debug("➡️ _compute_dates_logic appelé pour stay %s", rec.id)
        
        rec.planned_checkin_date = False
        rec.planned_checkout_date = False

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

        # Réservations flexibles : pas de calcul automatique
        if rec.reservation_type_id.is_flexible:
            _logger_booking.debug("ℹ️ Réservation flexible, pas de calcul auto.")
            return

        # Recherche du slot horaire
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

        # Calcul des dates planned
        rec.planned_checkin_date = datetime.combine(
            rec.booking_start_date, float_to_time(slot.checkin_time)
        )
        rec.planned_checkout_date = datetime.combine(
            rec.booking_end_date, float_to_time(slot.checkout_time)
        )

        _logger_booking.debug(
            "✅ Dates calculées: checkin=%s checkout=%s",
            rec.planned_checkin_date,
            rec.planned_checkout_date,
        )

        # Correction pour réservations classiques (checkout <= checkin)
        if (
            rec.reservation_type_id.code == "classic"
            and rec.planned_checkout_date <= rec.planned_checkin_date
        ):
            rec.planned_checkout_date += timedelta(days=1)
            _logger_booking.debug(
                "↪️ Correction appliquée (+1 jour) -> checkout=%s",
                rec.planned_checkout_date,
            )

        # ==================== VÉRIFICATION DE DISPONIBILITÉ ====================
        if not rec.room_type_id:
            _logger_booking.warning("⚠️ Aucun type de chambre défini, skip vérif dispo")
            return

        _logger_booking.info(
            "🔍 [AVAILABILITY] Vérification disponibilité | stay=%s | type=%s | in=%s | out=%s",
            rec.id or 'new',
            rec.room_type_id.id,
            rec.planned_checkin_date,
            rec.planned_checkout_date
        )

        # Récupération du buffer de nettoyage
        #try:
         #   buffer_hours = float(
          #      self.env['ir.config_parameter'].sudo().get_param(
           #         'hotel.cleaning_buffer_hours', default='0.5'
            #    )
            #)
        #except (ValueError, TypeError):
         #   buffer_hours = 0.5
          #  _logger_booking.warning("⚠️ Buffer par défaut utilisé: 2.0h")
            
        buffer_hours = 0.5

        # Appel au moteur de disponibilité
        try:
            availability_engine = self.env['hotel.room.availability.engine']
            availability_result = availability_engine.check_availability(
                room_type_id=rec.room_type_id.id,
                checkin_date=rec.planned_checkin_date,
                checkout_date=rec.planned_checkout_date,
                exclude_stay_id=rec.id if rec.id else None,
                buffer_hours=buffer_hours
            )

            _logger_booking.info(
                "📊 [AVAILABILITY] Résultat | stay=%s | status=%s | room=%s",
                rec.id or 'new',
                availability_result.get('status'),
                availability_result.get('room_name', 'N/A')
            )

            # Traitement selon le statut
            if availability_result['status'] == 'available':
                # Chambre disponible : attribution automatique si non assignée
                if availability_result.get('room_id') and not rec.room_id:
                    rec.room_id = availability_result['room_id']
                    _logger_booking.info(
                        "✅ [AVAILABILITY] Chambre assignée auto | room=%s",
                        availability_result.get('room_name')
                    )

            elif availability_result['status'] == 'unavailable':
                # Aucune chambre disponible : afficher les alternatives
                _logger_booking.warning(
                    "⚠️ [AVAILABILITY] Indisponible | message=%s",
                    availability_result.get('message')
                )
                
                alternatives = availability_result.get('alternatives', [])
                warning_msg = availability_result.get('message', 'Aucune chambre disponible.')
                
                if alternatives:
                    warning_msg += "\n\n" + _("Créneaux alternatifs disponibles :")
                    for idx, alt in enumerate(alternatives[:3], 1):
                        alt_in = alt['checkin'].strftime('%d/%m/%Y %H:%M')
                        alt_out = alt['checkout'].strftime('%d/%m/%Y %H:%M')
                        warning_msg += f"\n{idx}. Chambre {alt['room_name']}: {alt_in} → {alt_out}"
                
                # Retourner un warning pour informer l'utilisateur
                return {
                    'warning': {
                        'title': _('Disponibilité'),
                        'message': warning_msg
                    }
                }

            elif availability_result['status'] == 'error':
                # Erreur technique
                _logger_booking.error(
                    "❌ [AVAILABILITY] Erreur | message=%s",
                    availability_result.get('message')
                )
                return {
                    'warning': {
                        'title': _('Erreur'),
                        'message': availability_result.get('message', 
                                                        _('Erreur lors de la vérification'))
                    }
                }

        except Exception as e:
            _logger_booking.exception(
                "🔥 [AVAILABILITY] Exception lors de la vérification | stay=%s | err=%s",
                rec.id or 'new',
                str(e)
            )
            # Ne pas bloquer le processus en cas d'erreur technique
            return {
                'warning': {
                    'title': _('Erreur technique'),
                    'message': _('La vérification de disponibilité a échoué. Veuillez réessayer.')
                }
            }

        _logger_booking.debug("is_flexible_reservation=%s", rec.is_flexible_reservation)

    ### ----------- PERSISTANCE -------------
    @api.depends(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _compute_checkin_checkout(self):
        for rec in self:
            _logger_booking.debug(
                "🟢 _compute_checkin_checkout déclenché pour stay %s", rec.id
            )
            self._compute_dates_logic(rec)

    # ##----------- UX : CALCUL INSTANTANÉ DANS LE FORMULAIRE -------------
    @api.onchange(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _onchange_dates_and_type(self):
        for rec in self:
            _logger_booking.debug("🟠 _onchange_dates_and_type déclenché pour stay %s", rec.id)
            result = self._compute_dates_logic(rec)
            if result:
                return result

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

    # ----------- Calcul des prix en utilisant le moteur de pricing prix chambre + ec/lc -------------
    @api.depends(
        "room_type_id",
        "reservation_type_id",
        "planned_checkin_date",
        "planned_checkout_date",
        "occupant_ids",
    )
    def _compute_room_price_total(self):
        """
        Calcule le prix chambre en appelant le service tarifaire.
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

                rec.financial_summary_details = json.dumps(
                    result, ensure_ascii=False, indent=2, default=str
                )

                _logger.info(
                    "[CHECK FINANCIAL] stay=%s | financial_summary_details=%s",
                    rec.id,
                    rec.financial_summary_details,
                )
                _logger.info(
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

        return True

    """@api.depends(
        "pricing_price_base", "pricing_adjustments", "pricing_supplements"
    )
    def _compute_stay_financial_summary(self):
        for rec in self:
            # init
            subtotal = 0.0
            tax = 0.0  # pour l'instant
            details = {}

            # --- Base ---
            base_amount = rec.pricing_price_base or 0.0
            subtotal += base_amount
            details["base"] = {
                "label": "Prix de base",
                "amount": base_amount,
            }

            # --- Ajustements ---
            adjustments_list = []
            try:
                adjustments = json.loads(rec.pricing_adjustments or "[]")
                for adj in adjustments:
                    amt = adj.get("amount", 0.0)
                    subtotal += amt
                    adjustments_list.append({
                        "label": adj.get("label", "Ajustement"),
                        "amount": amt,
                    })
            except Exception:
                adjustments_list = []
            details["adjustments"] = adjustments_list

            # --- Suppléments ---
            supplements_list = []
            try:
                supplements = json.loads(rec.pricing_supplements or "[]")
                for sup in supplements:
                    amt = sup.get("amount", 0.0)
                    subtotal += amt
                    supplements_list.append({
                        "label": sup.get("label", "Supplément"),
                        "amount": amt,
                    })
            except Exception:
                supplements_list = []
            details["supplements"] = supplements_list

            # --- Remises (vide pour l'instant) ---
            details["discounts"] = []

            # --- Totaux ---
            total = subtotal + tax
            details["subtotal"] = subtotal
            details["tax"] = tax
            details["total"] = total

            # --- Assignation ---
            rec.price_subtotal = subtotal
            rec.price_tax = tax
            rec.price_total = total
            rec.financial_summary_details = json.dumps(details, ensure_ascii=False, indent=2)"""

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

    @api.depends("early_pricing_mode", "late_pricing_mode")
    def _compute_derive_eclc_pricing_mode(self):
        for rec in self:
            # Priorité : early > late ; si aucun, False
            rec.eclc_pricing_mode = (
                rec.early_pricing_mode or rec.late_pricing_mode or False
            )

    @api.model
    def create(self, vals):
        """S'assurer que actual = planned par défaut à la création"""
        if not vals.get("actual_checkin_date") and vals.get("planned_checkin_date"):
            vals["actual_checkin_date"] = vals["planned_checkin_date"]
        if not vals.get("actual_checkout_date") and vals.get("planned_checkout_date"):
            vals["actual_checkout_date"] = vals["planned_checkout_date"]

        return super().create(vals)

    def write(self, vals):
        """Si les dates prévues changent, on ajuste les actuals (sauf si déjà modifiées par EC/LC)"""
        for rec in self:
            if "planned_checkin_date" in vals and not rec.request_type:
                vals.setdefault("actual_checkin_date", vals["planned_checkin_date"])
            if "planned_checkout_date" in vals and not rec.request_type:
                vals.setdefault("actual_checkout_date", vals["planned_checkout_date"])
        return super().write(vals)

    @api.depends(
        "planned_checkin_date",
        "planned_checkout_date",
        "requested_checkin_datetime",
        "requested_checkout_datetime",
        "early_checkin_requested",
        "late_checkout_requested",
    )
    def _compute_actual_checkin_checkout(self):
        """
        Appelle le moteur ECLC pour *chacune* des demandes (early et late) et stocke
        le pricing_mode correspondant dans early_pricing_mode / late_pricing_mode.
        Attention : n'écrase plus un mode par l'autre.
        """
        engine = self.env["hotel.eclc.engine"]

        for rec in self:
            # Par défaut : actual = planned
            rec.actual_checkin_date = rec.planned_checkin_date
            rec.actual_checkout_date = rec.planned_checkout_date

            # Réinitialiser les champs de mode (important pour compute + store)
            rec.early_pricing_mode = False
            rec.late_pricing_mode = False
            rec.extra_night_required = False
            _logger.info(
                "[ACTUAL INIT] stay=%s planned_in=%s planned_out=%s",
                rec.id,
                rec.planned_checkin_date,
                rec.planned_checkout_date,
            )

            # --- Early Check-in ---
            if rec.early_checkin_requested and rec.requested_checkin_datetime:
                _logger.info(
                    "[EARLY REQUEST] stay=%s requested=%s planned=%s",
                    rec.id,
                    rec.requested_checkin_datetime,
                    rec.planned_checkin_date,
                )
                result = engine.evaluate_request(
                    request_type="early",
                    requested_datetime=rec.requested_checkin_datetime,
                    planned_datetime=rec.planned_checkin_date,
                    room_type_id=rec.room_type_id.id,
                )
                _logger.info("[EARLY RESULT] %s", result)

                # Stocker dans le champ dédié
                rec.early_pricing_mode = result.get("pricing_mode") or False

                if result.get("status") == "accepted":
                    rec.actual_checkin_date = rec.requested_checkin_datetime
                elif result.get("status") == "extra_night":
                    rec.extra_night_required = True

            # --- Late Check-out ---
            if rec.late_checkout_requested and rec.requested_checkout_datetime:
                _logger.info(
                    "[LATE REQUEST] stay=%s requested=%s planned=%s",
                    rec.id,
                    rec.requested_checkout_datetime,
                    rec.planned_checkout_date,
                )
                result = engine.evaluate_request(
                    request_type="late",
                    requested_datetime=rec.requested_checkout_datetime,
                    planned_datetime=rec.planned_checkout_date,
                    room_type_id=rec.room_type_id.id,
                )
                _logger.info("[LATE RESULT] %s", result)

                rec.late_pricing_mode = result.get("pricing_mode") or False

                if result.get("status") == "accepted":
                    rec.actual_checkout_date = rec.requested_checkout_datetime
                elif result.get("status") == "extra_night":
                    rec.extra_night_required = True

            _logger.info(
                "[ACTUAL FINAL] stay=%s actual_in=%s actual_out=%s early_mode=%s late_mode=%s",
                rec.id,
                rec.actual_checkin_date,
                rec.actual_checkout_date,
                rec.early_pricing_mode,
                rec.late_pricing_mode,
            )

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

    # ec lc après la resa à géer après
    def apply_eclc_pricing(self):
        """
        Gère le calcul tarifaire spécifique pour Early Check-in / Late Check-out.
        - Utilise le pricing_mode déjà stocké (eclc_pricing_mode).
        - Transmet ce pricing_mode + requested_datetime au moteur de pricing.
        - Met à jour les champs pricing du stay.
        """
        for rec in self:
            if (
                not rec.request_type
                or not rec.room_type_id
                or not rec.reservation_type_id
            ):
                _logger.debug(
                    "[ECLC][SKIP] Pas de demande horaire ou données incomplètes | stay=%s",
                    rec.id,
                )
                continue

            pricing_mode = rec.eclc_pricing_mode
            if not pricing_mode or pricing_mode == "invalid_request":
                _logger.debug(
                    "[ECLC][SKIP] Aucun pricing_mode valide | stay=%s",
                    rec.id,
                )
                continue

            # 👇 détermine requested_datetime pour les logs et pour compute_price
            requested_datetime = None
            if rec.request_type == "early":
                requested_datetime = (
                    rec.requested_checkin_datetime or rec.planned_checkin_date
                )
            elif rec.request_type == "late":
                requested_datetime = (
                    rec.requested_checkout_datetime or rec.planned_checkout_date
                )

            _logger.info(
                "[ECLC] Recalcule pricing (après résa) | stay=%s | mode=%s | requested=%s",
                rec.id,
                pricing_mode,
                requested_datetime,
            )

            pricing_service = self.env["hotel.pricing.service"]
            result = pricing_service.compute_price(
                room_type_id=rec.room_type_id.id,
                reservation_type_id=rec.reservation_type_id.id,
                planned_checkin_date=rec.planned_checkin_date,
                planned_checkout_date=rec.planned_checkout_date,
                nb_persons=len(rec.occupant_ids) or 1,
                pricing_mode=pricing_mode,
                requested_datetime=requested_datetime,  # 👈 NOUVEAU
            )

            if isinstance(result, dict):
                base_data = result.get("base", {})
                rec.pricing_price_base = float(base_data.get("amount", 0.0))
                rec.room_price_total = float(result.get("total", 0.0))
                rec.pricing_rule_id = base_data.get("rule_id") or False
                rec.pricing_adjustments = json.dumps(
                    result.get("adjustments", []), ensure_ascii=False, indent=2
                )
                rec.pricing_supplements = json.dumps(
                    result.get("supplements", []), ensure_ascii=False, indent=2
                )

                _logger.info(
                    "[ECLC][OK] stay=%s | mode=%s | total=%s",
                    rec.id,
                    pricing_mode,
                    rec.room_price_total,
                )
            else:
                _logger.error(
                    "[ECLC][ERR] Résultat pricing non valide | stay=%s | result=%s",
                    rec.id,
                    result,
                )

    @api.depends(
        "planned_checkin_date",
        "planned_checkout_date",
        "requested_checkin_datetime",
        "requested_checkout_datetime",
        "request_type",
        "room_type_id",
        "reservation_type_id",
    )
    def _compute_eclc_pricing(self):
        """
        Calcul tarifaire spécifique EC/LC, déclenché automatiquement
        quand les données horaires ou le type de demande changent.
        """
        for rec in self:
            rec.apply_eclc_pricing()

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
   

    