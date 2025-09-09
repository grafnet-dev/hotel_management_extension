import json
#import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time
from ..constants.booking_stays_state import STAY_STATES
from ..logging_config import eclc_logger as _logger



def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)





class HotelBookingStayS(models.Model):
    _name = "hotel.booking.stay"
    _description = "Séjour individuel de chaque reservation (booking)"
    # _rec_name = 'room_id' -> ici à faire de recherche et comprendre son utilité

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
    original_reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type d'origine",
        help="Type de réservation sélectionné initialement avant requalification flexible.",
        readonly=True,
        copy=False,
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
        compute="_compute_is_flexible_reservation", store=False
    )

    # Gestion du early check-in et late check-out
    early_checkin_requested = fields.Boolean("Early Check-in demandé")
    late_checkout_requested = fields.Boolean("Late Check-out demandé")
    # Heure exacte demandée par le client early checkin
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
    request_type = fields.Selection(
        [("early", "Early Check-in"), ("late", "Late Check-out")],
        string="Type de demande horaire",
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
    
    eclc_status = fields.Selection([
        ("accepted", "Acceptée"),
        ("refused", "Refusée"),
        ("pending", "En attente"),
    ], string="Statut EC/LC")

    eclc_pricing_mode = fields.Selection([
        ("early_fee", "Early check-in payant"),
        ("late_fee", "Late check-out payant"),
        ("extra_night", "Nuit supplémentaire"),
        ("invalid_request", "Requête invalide"),
    ], 
    string="Mode tarifaire EC/LC",
    compute="_compute_actual_checkin_checkout", store=True)
    
    early_checkin_price = fields.Float(
    string="Prix Early Check-in",
    default=0.0,
    readonly=True
)
    late_checkout_price = fields.Float(
        string="Prix Late Checkout",
        default=0.0,
        readonly=True
    )


    # Durée & Unité

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

    pricing_price_base = fields.Float(string="Prix de base", readonly=True)

    pricing_adjustments = fields.Text(
        string="Ajustements appliqués",
        readonly=True,
        help="Stocke en JSON les détails des ajustements (supplément extra guest, etc.)",
    )

    room_price_total = fields.Monetary(
        string="Prix chambre",
        compute="_compute_room_price_total",
        store=True,
        currency_field="currency_id",
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
        self.state = STAY_STATES["COMPLETED"]

    def action_cancel(self):
        self.state = STAY_STATES["CANCELLED"]

    def _set_default_uom_id(self):
        return self.env.ref("uom.product_uom_day")

    # Onchange = confort utilisateur
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

    # calcul automatique (methode à adapter plus tard)
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

    @api.depends("reservation_type_id")
    def _compute_is_flexible_reservation(self):
        for rec in self:
            rec.is_flexible_reservation = bool(rec.reservation_type_id.is_flexible)

    # ----------- Calcul des dates en fonction du type de resa -------------
    def _compute_dates_logic(self, rec):
        """
        Logique partagée entre compute et onchange
        Recalcule automatiquement planned_checkin_date et planned_checkout_date en fonction du type de réservation.

        """
        rec.planned_checkin_date = False
        rec.planned_checkout_date = False

        if (
            not rec.booking_start_date
            or not rec.booking_end_date
            or not rec.reservation_type_id
        ):
            return

        if rec.reservation_type_id.is_flexible:
            # Flexible = l'utilisateur saisit directement
            return

        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_type_id", "=", rec.room_type_id.id),
                ("reservation_type_id", "=", rec.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            return

        rec.planned_checkin_date = datetime.combine(
            rec.booking_start_date, float_to_time(slot.checkin_time)
        )
        rec.planned_checkout_date = datetime.combine(
            rec.booking_end_date, float_to_time(slot.checkout_time)
        )

        # Cas classique : checkout <= checkin -> +1 jour
        if (
            rec.reservation_type_id.code == "classic"
            and rec.planned_checkout_date <= rec.planned_checkin_date
        ):
            rec.planned_checkout_date += timedelta(days=1)

    # ----------- PERSISTANCE -------------
    @api.depends(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _compute_checkin_checkout(self):
        for rec in self:
            self._compute_dates_logic(rec)

    # ----------- UX : CALCUL INSTANTANÉ DANS LE FORMULAIRE -------------
    @api.onchange(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _onchange_dates_and_type(self):
        for rec in self:
            self._compute_dates_logic(rec)


    @api.onchange("early_checkin_requested", "late_checkout_requested")
    def _onchange_eclc_requested(self):
        """
        Synchronise les cases à cocher avec le pricing.
        Si les deux sont cochées, on calcule les deux séparément.
        """
        for rec in self:
            # Si aucune demande → reset complet
            if not rec.early_checkin_requested and not rec.late_checkout_requested:
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
                rec._compute_room_price_total()
                continue

            if rec.late_checkout_requested and not rec.early_checkin_requested:
                rec.request_type = "late"
                rec._compute_room_price_total()
                continue

            # Si les deux cochés → recalcul double
            if rec.early_checkin_requested and rec.late_checkout_requested:
                # Calcul séparé Early
                rec.request_type = "early"
                rec._compute_room_price_total()
                early_price = rec.early_checkin_price

                # Calcul séparé Late
                rec.request_type = "late"
                rec._compute_room_price_total()
                late_price = rec.late_checkout_price

                # On additionne les deux
                rec.room_price_total = rec.pricing_price_base + early_price + late_price

                # Remise à zéro du request_type pour éviter d'écraser les horaires
                rec.request_type = False

    # ----------- Calcul des prix en utilisant le moteur de pricing -------------
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
        Si une demande EC/LC est présente pendant la réservation,
        on évalue d'abord ECLC pour récupérer un pricing_mode,
        puis on le transmet au moteur de pricing.
        """
        for rec in self:
            # Reset par défaut
            rec.room_price_total = 0.0
            rec.pricing_rule_id = False
            rec.pricing_adjustments = False
            rec.pricing_price_base = 0.0

            ctx = {
                "stay_id": rec.id or None,
                "booking_id": rec.booking_id.id if rec.booking_id else None,
                "room_type_id": rec.room_type_id.id if rec.room_type_id else None,
                "reservation_type_id": rec.reservation_type_id.id if rec.reservation_type_id else None,
                "planned_checkin_date": rec.planned_checkin_date and rec.planned_checkin_date.isoformat(),
                "planned_checkout_date": rec.planned_checkout_date and rec.planned_checkout_date.isoformat(),
                "nb_persons": len(rec.occupant_ids) or 1,
                "user_tz": self.env.user.tz,
            }

            if not (
                rec.room_type_id
                and rec.reservation_type_id
                and rec.planned_checkin_date
                and rec.planned_checkout_date
            ):
                _logger.debug(
                    "[PRICING][SKIP] Inputs incomplets pour stay=%s | ctx=%s",
                    rec.id or "new",
                    json.dumps(ctx, ensure_ascii=False),
                )
                continue

            #  si une demande EC/LC est déjà saisie pendant la résa,
            # on récupère un pricing_mode AVANT d'appeler le moteur pricing.
            pricing_mode = None
            requested_datetime = None
            if rec.request_type and rec.room_type_id:
                engine = self.env["hotel.eclc.engine"]

                if rec.request_type == "early":
                    requested_datetime = rec.requested_checkin_datetime or rec.planned_checkin_date
                    planned_datetime = rec.planned_checkin_date
                elif rec.request_type == "late":
                    requested_datetime = rec.requested_checkout_datetime or rec.planned_checkout_date
                    planned_datetime = rec.planned_checkout_date
                else:
                    requested_datetime = None
                    planned_datetime = None

                if requested_datetime and planned_datetime:
                    _logger.info("🔎 [ECLC][INLINE] Évaluation pendant pricing initial")
                    eclc_result = engine.evaluate_request(
                        request_type=rec.request_type,
                        requested_datetime=requested_datetime,
                        planned_datetime=planned_datetime,
                        room_type_id=rec.room_type_id.id,
                    )
                    pricing_mode = eclc_result.get("pricing_mode")
                    _logger.info(
                        "[ECLC][INLINE][OK] stay=%s | request_type=%s | requested=%s | planned=%s | mode=%s",
                        rec.id or "new",
                        rec.request_type,
                        requested_datetime,
                        planned_datetime,
                        pricing_mode,
                    )
                else:
                    _logger.debug(
                        "[ECLC][INLINE][SKIP] Dates manquantes pour stay=%s (request_type=%s)",
                        rec.id or "new",
                        rec.request_type,
                    )
            # ======== fin ajout ECLC inline

            try:
                result = self.env["hotel.pricing.service"].compute_price(
                    room_type_id=rec.room_type_id.id,
                    reservation_type_id=rec.reservation_type_id.id,
                    planned_checkin_date=rec.planned_checkin_date,
                    planned_checkout_date=rec.planned_checkout_date,
                    nb_persons=len(rec.occupant_ids) or 1,
                    pricing_mode=pricing_mode,
                    requested_datetime=requested_datetime,
                )

                _logger.info(
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

                base_data = result.get("base", {})
                rec.pricing_price_base = float(base_data.get("amount", 0.0))
                rec.room_price_total = float(result.get("total", 0.0))
                rec.pricing_rule_id = base_data.get("rule_id") or False
                rec.pricing_adjustments = json.dumps(
                    result.get("adjustments", []), ensure_ascii=False, indent=2
                )

                _logger.info(
                    "[PRICING][OK] stay=%s | base=%s | total=%s | rule_id=%s | adjustments=%s",
                    rec.id,
                    rec.pricing_price_base,
                    rec.room_price_total,
                    rec.pricing_rule_id,
                    rec.pricing_adjustments,
                )

            except Exception as e:
                _logger.exception(
                    "[PRICING][EXC] Erreur compute_price pour stay=%s | ctx=%s | err=%s",
                    rec.id,
                    json.dumps(ctx, ensure_ascii=False),
                    e,
                )
                # On laisse room_price_total à 0.0; pas de raise pour ne pas bloquer l'UI


    # ---------- Gestion des EC LC ----------
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
        "request_type",
        "room_type_id",
    )
    def _compute_actual_checkin_checkout(self):
        for rec in self:
            # Par défaut : actual = planned
            rec.actual_checkin_date = rec.planned_checkin_date
            rec.actual_checkout_date = rec.planned_checkout_date

            # Si pas de demande spéciale → pas de calcul EC/LC
            if not rec.request_type or not rec.room_type_id:
                continue

            engine = self.env["hotel.eclc.engine"]

            if rec.request_type == "early":
                requested_datetime = (
                    rec.requested_checkin_datetime or rec.planned_checkin_date
                )
                planned_datetime = rec.planned_checkin_date

            elif rec.request_type == "late":
                requested_datetime = (
                    rec.requested_checkout_datetime or rec.planned_checkout_date
                )
                planned_datetime = rec.planned_checkout_date

            else:
                continue

            # Appel du moteur EC/LC
            result = engine.evaluate_request(
                request_type=rec.request_type,
                requested_datetime=requested_datetime,
                planned_datetime=planned_datetime,
                room_type_id=rec.room_type_id.id,
            )

            # 🔑 Enregistrer le mode tarifaire renvoyé
            rec.eclc_pricing_mode = result.get("pricing_mode") or "invalid_request"
            # Si accepté → on ajuste les horaires effectifs
            if result.get("status") == "accepted":
                if rec.request_type == "early":
                    rec.actual_checkin_date = requested_datetime
                elif rec.request_type == "late":
                    rec.actual_checkout_date = requested_datetime

            # Si nuit supplémentaire requise → on garde les planned par défaut
            elif result.get("status") == "extra_night":
                rec.extra_night_required = True

            # Si refusé → on ne touche pas aux planned


    @api.depends(
        "requested_checkin_datetime",
        "requested_checkout_datetime",
        "planned_checkin_date",
        "planned_checkout_date",
        "request_type",
    )
    def _compute_difference_hours(self):
        for rec in self:
            rec.difference_hours = 0.0

            if (
                rec.request_type == "early"
                and rec.requested_checkin_datetime
                and rec.planned_checkin_date
            ):
                diff = (
                    rec.planned_checkin_date - rec.requested_checkin_datetime
                ).total_seconds() / 3600.0
                rec.difference_hours = max(diff, 0.0)  # Pas de valeurs négatives

            elif (
                rec.request_type == "late"
                and rec.requested_checkout_datetime
                and rec.planned_checkout_date
            ):
                diff = (
                    rec.requested_checkout_datetime - rec.planned_checkout_date
                ).total_seconds() / 3600.0
                rec.difference_hours = max(diff, 0.0)



    def apply_eclc_pricing(self):
        """
        Gère le calcul tarifaire spécifique pour Early Check-in / Late Check-out.
        - Utilise le pricing_mode déjà stocké (eclc_pricing_mode).
        - Transmet ce pricing_mode + requested_datetime au moteur de pricing.
        - Met à jour les champs pricing du stay.
        """
        for rec in self:
            if not rec.request_type or not rec.room_type_id or not rec.reservation_type_id:
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
                requested_datetime = rec.requested_checkin_datetime or rec.planned_checkin_date
            elif rec.request_type == "late":
                requested_datetime = rec.requested_checkout_datetime or rec.planned_checkout_date

            _logger.info(
                "[ECLC] Recalcule pricing (après résa) | stay=%s | mode=%s | requested=%s",
                rec.id, pricing_mode, requested_datetime
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
 