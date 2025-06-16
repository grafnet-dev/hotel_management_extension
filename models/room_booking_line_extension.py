from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class RoomBookingLine(models.Model):
    _inherit = "room.booking.line"

    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        help="Type de réservation sélectionné pour cette chambre",
    )

    booking_date = fields.Date(
        string="Date de réservation",
        help="Date utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )
    
    booking_end_date = fields.Date(
    string="Date de fin de réservation",
    help="Date de fin utilisée pour calculer la date de départ pour les réservations sur plusieurs nuitées",
    )


    # filtrer les types en fonction de la chambre sélectionnée room_id
    @api.onchange("room_id")
    def _onchange_room_id(self):
        if self.room_id:
            return {
                "domain": {
                    "reservation_type_id": [
                        ("id", "in", self.room_id.reservation_type_ids.ids)
                    ]
                }
            }
        else:
            return {"domain": {"reservation_type_id": []}}

    # Automatisme principal : remplissage des dates selon le type de reservation
    @api.onchange("reservation_type_id", "booking_date", "booking_end_date", "room_id")
    def _onchange_auto_fill_dates(self):
        self.checkin_date = False
        self.checkout_date = False

        if not self.reservation_type_id or not self.room_id or not self.booking_date:
            return

        if self.reservation_type_id.is_flexible:
            # Ne rien remplir automatiquement
            return

        # Cherche un slot défini pour cette chambre et ce type
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_id", "=", self.room_id.id),
                ("reservation_type_id", "=", self.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            return  # Aucun slot trouvé → pas de remplissage automatique

        try:
            # Construit le check-in
            checkin_dt = datetime.combine(self.booking_date, slot.start_time)

            if self.reservation_type_id.code == "classic" and self.booking_end_date:
                # Pour plusieurs nuitées, checkout = date de fin à l'heure de fin
                checkout_dt = datetime.combine(self.booking_end_date, slot.end_time)
            else:
                # Par défaut, checkout le même jour (day use)
                checkout_dt = datetime.combine(self.booking_date, slot.end_time)

                # Pour les nuitées avec checkout avant checkin, on décale d'un jour
                if self.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                    checkout_dt += timedelta(days=1)

            self.checkin_date = checkin_dt
            self.checkout_date = checkout_dt
             # En cas de problème de conversion (rare mais prudent)
        except Exception as e:
            raise ValidationError(_("Erreur lors du calcul des horaires : %s") % str(e))


    # Validation (ex. dates obligatoires sauf si flexible)
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
                if not rec.checkin_date or not rec.checkout_date:
                    raise ValidationError(
                        "Pour une réservation flexible, les dates doivent être saisies manuellement."
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
                    _("La date de fin de réservation ne peut pas être antérieure à la date de début.")
                )

