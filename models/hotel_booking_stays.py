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
    ## Datetimes calculés ou saisis
    checkin_date = fields.Datetime(
        string="Check In",
        help="computed based on booking date and room's reservation type slot , or user input for flexible type",
        compute="_compute_checkin_checkout",
        store=True,
    )

    checkout_date = fields.Datetime(
        string="Check Out",
        help="computed based on booking date and room's reservation type slot , or user input for flexible type",
        compute="_compute_checkin_checkout",
        store=True,
    )
    ##champs ajoutés pour la gestion dyanmque de la vue dans le xml
    is_flexible_reservation = fields.Boolean(
        compute="_compute_is_flexible_reservation", store=False
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
    extra_night_required = fields.Boolean(
        string="Nuit supplémentaire requise", default=False
    )
    # Distinguer flexible manuel vs automatique
    is_manual_flexible = fields.Boolean(
        "Flexible sélectionné manuellement",
        help="True si l'utilisateur a directement sélectionné le type flexible, False si requalification automatique",
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
    currency_id = fields.Many2one(
        string="Currency",
        related="booking_id.pricelist_id.currency_id",
        help="The currency used",
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
        [
            ("draft", "Brouillon"),
            ("ongoing", "En cours"),
            ("checked_out", "Sorti"),
            ("cancelled", "Annulé"),
        ],
        string="État",
        default="draft",
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
        self.state = "ongoing"

    def action_checkout(self):
        self.state = "checked_out"

    def action_cancel(self):
        self.state = "cancelled"

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

        if self.extra_night_required:
            return {
                "warning": {
                    "title": "Attention : Nuit Supplémentaire",
                    "message": "L'horaire demandé sort des limites standards. Une nuit supplémentaire sera peut-être requise.",
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

    # ----------- LOGIQUE COMMUNE -------------
    def _compute_dates_logic(self, rec):
        """
        Logique partagée entre compute et onchange
        Recalcule automatiquement checkin_date et checkout_date en fonction du type de réservation.

        """
        rec.checkin_date = False
        rec.checkout_date = False

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

        rec.checkin_date = datetime.combine(
            rec.booking_start_date, float_to_time(slot.checkin_time)
        )
        rec.checkout_date = datetime.combine(
            rec.booking_end_date, float_to_time(slot.checkout_time)
        )

        # Cas classique : checkout <= checkin -> +1 jour
        if (
            rec.reservation_type_id.code == "classic"
            and rec.checkout_date <= rec.checkin_date
        ):
            rec.checkout_date += timedelta(days=1)

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

    

    @api.depends("room_type_id", "reservation_type_id", "booking_start_date", "booking_end_date")
    def _compute_room_price_total(self):
        for stay in self:
            stay.room_price_total = 0.0

            # Vérification des infos nécessaires
            if not (stay.room_type_id and stay.reservation_type_id and stay.booking_start_date and stay.booking_end_date):
                continue

            # Récupération de la règle tarifaire
            pricing_rule = self.env["hotel.room.pricing"].search([
                ("room_type_id", "=", stay.room_type_id.id),
                ("reservation_type_id", "=", stay.reservation_type_id.id),
                ("active", "=", True)
            ], limit=1)

            if not pricing_rule:
                stay.room_price_total = 0.0
                continue

            # Calcul de la durée en heures
            duration_days = (stay.booking_end_date - stay.booking_start_date).days or 1
            duration_hours = duration_days * 24

            # Prix de base = prix standard du type de chambre (si défini)
            base_price = stay.room_type_id.base_price or 0.0

            # Utilisation de la méthode compute_price pour centraliser la logique
            stay.room_price_total = pricing_rule.compute_price(
                base_price=base_price,
                duration_hours=duration_hours
            )

            # Si le mode n'est pas horaire, on multiplie par le nombre de jours
            if pricing_rule.pricing_mode != "hourly":
                stay.room_price_total *= duration_days
