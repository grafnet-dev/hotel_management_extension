from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time


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
        "hotel_booking_stay_res_partner_rel",  # nom de la table de relation
        "stay_id",  # clé étrangère vers hotel.booking.stay
        "partner_id",  # clé étrangère vers res.partner
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
    room_id = fields.Many2one(
        "hotel.room", string="Room", help="Indicates the Room", required=True
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
    checkin_date = fields.Datetime(
        string="Check In",
        help="You can choose the date," " Otherwise sets to current Date",
        required=True,
    )

    checkout_date = fields.Datetime(
        string="Check Out",
        help="You can choose the date," " Otherwise sets to current Date",
        required=True,
    )
    booking_date = fields.Date(
        string="Date de réservation",
        help="Date utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )

    booking_end_date = fields.Date(
        string="Date de fin de réservation",
        help="Date de fin utilisée pour calculer la date de départ pour les réservations sur plusieurs nuitées",
    )

    # Gestion du early check-in et late check-out
    early_checkin_requested = fields.Boolean("Early Check-in demandé")
    late_checkout_requested = fields.Boolean("Late Check-out demandé")
    early_checkin_hour = fields.Float("Heure Early Check-in", help="Ex: 10.5 = 10h30")
    early_checkin_time_display = fields.Datetime(
        string="Heure Early Check-in (affichée)",
        
        
        store=False,
    )

    late_checkout_hour = fields.Float("Heure Late Check-out")
    late_checkout_time_display = fields.Datetime(
        string="Heure Late Check-out (affichée)",
    
        store=False,
    )
    requalification_reason = fields.Char("Motif de requalification")
    # Stocker le résultat de la requalification automatique
    was_requalified_flexible = fields.Boolean("Requalifié en Flexible")
    extra_night_required = fields.Boolean(string="Nuit supplémentaire requise", default=False)
    #Distinguer flexible manuel vs automatique
    is_manual_flexible = fields.Boolean(
        "Flexible sélectionné manuellement",
        help="True si l'utilisateur a directement sélectionné le type flexible, False si requalification automatique"
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
    need_food = fields.Boolean("Need Food")
    food_order_line_ids = fields.One2many(
        "food.booking.line", "booking_id", string="Food Order Lines", copy=True
    )

    need_service = fields.Boolean("Need Services")
    service_booking_line_ids = fields.One2many(
        "service.booking.line", "booking_id", string="Service Booking Lines", copy=True
    )

    need_fleet = fields.Boolean("Need Fleet")
    fleet_booking_line_ids = fields.One2many(
        "fleet.booking.line", "booking_id", string="Fleet Booking Lines", copy=True
    )

    need_event = fields.Boolean("Need Event")
    event_booking_line_ids = fields.One2many(
        "event.booking.line", "booking_id", string="Event Booking Lines", copy=True
    )

    # Prix & Facturation -> à définir les champs nécessaires plus tard et logique de calcul
    price_unit = fields.Float(
        related="room_id.list_price",
        string="Rent",
        digits="Product Price",
        help="The rent price of the selected room.",
    )

    currency_id = fields.Many2one(
        string="Currency",
        related="booking_id.pricelist_id.currency_id",
        help="The currency used",
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

    # États & Suivi -> à définir aussi
    state = fields.Selection(
        related="booking_id.state",
        string="Order Status",
        help=" Status of the Order",
        copy=False,
    )

   
    
    # Méthode pour calculer les noms des occupants
    @api.depends("occupant_ids")
    def _compute_occupant_names(self):
        for stay in self:
            stay.occupant_names = (
                ", ".join(stay.occupant_ids.mapped("name")) if stay.occupant_ids else ""
            )


   

    def _set_default_uom_id(self):
        return self.env.ref("uom.product_uom_day")

    # Onchange = confort utilisateur
    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        if (
            self.checkin_date
            and self.checkout_date
            and self.checkout_date < self.checkin_date
        ):
            self.checkout_date = self.checkin_date + timedelta(days=1)
            return {
                "warning": {
                    "title": _("Correction automatique"),
                    "message": _(
                        "La date de départ a été ajustée car elle était avant la date d'arrivée."
                    ),
                }
            }


    # calcul automatique
    @api.depends("checkin_date", "checkout_date")
    def _compute_duration(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                diff = rec.checkout_date - rec.checkin_date
                rec.uom_qty = diff.days + (1 if diff.total_seconds() > 0 else 0)
            else:
                rec.uom_qty = 0


    # Constraint = validation cohérence dates
    @api.constrains("checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if (
                rec.checkin_date
                and rec.checkout_date
                and rec.checkout_date < rec.checkin_date
            ):
                raise ValidationError(
                    _("La date de départ ne peut pas être avant la date d'arrivée.")
                )


    # Constraint = validation disponibilité
    @api.constrains("checkin_date", "checkout_date", "room_id")
    def _check_room_availability(self):
        for line in self:
            if not line.checkin_date or not line.checkout_date or not line.room_id:
                continue
            records = self.env["room.booking"].search(
                [
                    ("state", "in", ["reserved", "check_in"]),
                    ("room_line_ids.room_id", "=", line.room_id.id),
                ]
            )
            for rec in records:
                if rec.id == line.booking_id.id:
                    continue
                for rec_line in rec.room_line_ids:
                    if (
                        rec_line.checkin_date <= line.checkin_date <= rec_line.checkout_date
                        or rec_line.checkin_date
                        <= line.checkout_date
                        <= rec_line.checkout_date
                        or (
                            line.checkin_date <= rec_line.checkin_date
                            and line.checkout_date >= rec_line.checkout_date
                        )
                    ):
                        raise ValidationError(
                            _("La chambre est déjà réservée sur ces dates.")
                        )
    #  Requalification & calcul automatique

    def _auto_check_qualification(self):
        """
        Logique de requalification et détection de nuit supplémentaire
        """
        for rec in self:
            if not rec.room_id:
                continue

            # Réinitialise les champs d'état
            rec.was_requalified_flexible = False
            rec.extra_night_required = False
            rec.requalification_reason = False

            # Récupère les heures limites depuis la configuration de la chambre
            early_limit = rec.room_id.early_checkin_hour_limit or 6.0
            late_limit = rec.room_id.late_checkout_hour_limit or 18.0

            reasons = []

            # Cas 1 : Early check-in
            if rec.early_checkin_requested and rec.early_checkin_hour not in [
                None,
                0.0,
            ]:
                if rec.early_checkin_hour < early_limit:
                    rec.extra_night_required = True
                    reasons.append(
                        f"Early Check-in à {rec.early_checkin_hour}h < limite {early_limit}h"
                    )
                else:
                    rec.was_requalified_flexible = True
                    reasons.append(
                        f"Early Check-in demandé à {rec.early_checkin_hour}h"
                    )

            # Cas 2 : Late check-out
            if rec.late_checkout_requested and rec.late_checkout_hour not in [
                None,
                0.0,
            ]:
                if rec.late_checkout_hour > late_limit:
                    rec.extra_night_required = True
                    reasons.append(
                        f"Late Check-out à {rec.late_checkout_hour}h > limite {late_limit}h"
                    )
                else:
                    rec.was_requalified_flexible = True
                    reasons.append(
                        f"Late Check-out demandé à {rec.late_checkout_hour}h"
                    )

            # : Gestion du retour au type original
            if not rec.early_checkin_requested and not rec.late_checkout_requested:
                # Aucune demande early/late active → revenir au type original
                if rec.original_reservation_type_id:
                    rec.reservation_type_id = rec.original_reservation_type_id
                    rec.original_reservation_type_id = False
                    rec.was_requalified_flexible = False
                    rec.requalification_reason = False
                    rec.is_manual_flexible = False  # ✅ Réinitialiser le flag manuel
            else:
                # Il y a des demandes early/late → basculer en flexible si nécessaire
                if reasons:
                    rec.requalification_reason = " | ".join(reasons)

                    if (
                        rec.reservation_type_id
                        and not rec.reservation_type_id.is_flexible
                    ):
                        # Mémoriser le type original si pas encore fait
                        if not rec.original_reservation_type_id:
                            rec.original_reservation_type_id = rec.reservation_type_id

                        # Chercher et assigner le type flexible
                        flexible_type = self.env["hotel.reservation.type"].search(
                            [("is_flexible", "=", True)], limit=1
                        )
                        if flexible_type:
                            rec.reservation_type_id = flexible_type
                            rec.was_requalified_flexible = True
                            rec.is_manual_flexible = (
                                False  # ✅ Flexible automatique, pas manuel
                            )

            #  ÉTAPE 3: Recalcul des horaires après tous les changements
            rec.recalculate_checkin_checkout_dates()

    def recalculate_checkin_checkout_dates(self):
        """
        Recalcule les champs checkin_date et checkout_date
        en tenant compte des demandes early/late et des heures personnalisées.
        """
        for rec in self:
            if not rec.booking_date or not rec.room_id or not rec.reservation_type_id:
                continue

            #  Ne pas toucher aux dates si flexible manuel
            if rec.reservation_type_id.is_flexible and rec.is_manual_flexible:
                # L'utilisateur a sélectionné flexible manuellement
                # → Il doit saisir les dates lui-même, on ne calcule rien
                return

            try:
                # ✅ Pour les flexibles automatiques (requalification), on calcule
                if rec.reservation_type_id.is_flexible and not rec.is_manual_flexible:
                    # Flexible automatique : on cherche le slot du type original
                    slot = None
                    if rec.original_reservation_type_id:
                        slot = rec.env["hotel.room.reservation.slot"].search(
                            [
                                ("room_id", "=", rec.room_id.id),
                                (
                                    "reservation_type_id",
                                    "=",
                                    rec.original_reservation_type_id.id,
                                ),
                            ],
                            limit=1,
                        )

                    if not slot:
                        raise ValidationError(
                            _(
                                "Impossible de calculer les horaires pour la requalification flexible."
                            )
                        )
                else:
                    # Type non-flexible : slot normal
                    slot = rec.env["hotel.room.reservation.slot"].search(
                        [
                            ("room_id", "=", rec.room_id.id),
                            ("reservation_type_id", "=", rec.reservation_type_id.id),
                        ],
                        limit=1,
                    )

                    if not slot:
                        raise ValidationError(
                            _(
                                "Aucun créneau horaire défini pour cette chambre et ce type de réservation."
                            )
                        )

                # Déterminer l'heure de check-in
                if rec.early_checkin_requested and rec.early_checkin_hour not in [
                    None,
                    0.0,
                ]:
                    checkin_time = float_to_time(rec.early_checkin_hour)
                else:
                    checkin_time = float_to_time(slot.checkin_time)

                checkin_dt = datetime.combine(rec.booking_date, checkin_time)

                # Déterminer la date et l'heure de checkout
                if rec.reservation_type_id.code == "classic" and rec.booking_end_date:
                    checkout_base_date = rec.booking_end_date
                else:
                    checkout_base_date = rec.booking_date

                if rec.late_checkout_requested and rec.late_checkout_hour not in [
                    None,
                    0.0,
                ]:
                    checkout_time = float_to_time(rec.late_checkout_hour)
                else:
                    checkout_time = float_to_time(slot.checkout_time)

                checkout_dt = datetime.combine(checkout_base_date, checkout_time)

                # Corriger si checkout <= checkin (pour les nuitées)
                if (
                    rec.reservation_type_id.code == "classic"
                    and checkout_dt <= checkin_dt
                ):
                    checkout_dt += timedelta(days=1)

                rec.checkin_date = checkin_dt
                rec.checkout_date = checkout_dt

            except Exception as e:
                raise ValidationError(
                    _("Erreur dans le calcul des horaires personnalisés : %s") % str(e)
                    )

    # Warning si extra_night_required est True
    @api.onchange("extra_night_required")
    def _onchange_alert_extra_night(self):
        if self.extra_night_required:
            return {
                "warning": {
                    "title": "Attention : Nuit Supplémentaire",
                    "message": "L'horaire demandé sort des limites standards. Une nuit supplémentaire sera peut-être requise.",
                }
            }

    #  Validation cohérente pour les flexibles
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        """
        Pour les réservations flexibles, on recommande la saisie manuelle mais on ne l'impose pas forcément
        """
        for rec in self:
            # On peut ajouter des validations spécifiques selon les besoins métier
            # Par exemple : empêcher la sauvegarde si checkin > checkout
            if (
                rec.checkin_date
                and rec.checkout_date
                and rec.checkout_date < rec.checkin_date
            ):
                raise ValidationError(
                    _(
                        "La date de départ ne peut pas être antérieure à la date d'arrivée."
                    )
                )

    @api.constrains("booking_date", "booking_end_date", "reservation_type_id")
    def _check_booking_dates_order(self):
        for rec in self:
            if (
                rec.reservation_type_id
                and rec.reservation_type_id.code == "classic"
                and rec.booking_date
                and rec.booking_end_date
                and rec.booking_end_date < rec.booking_date
            ):
                raise ValidationError(
                    _(
                        "La date de fin de réservation ne peut pas être antérieure à la date de début."
                    )
                )
