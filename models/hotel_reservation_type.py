from odoo import models, fields


class HotelReservationType(models.Model):
    _name = "hotel.reservation.type"
    _description = "Type de réservation"

    name = fields.Char("Nom du type", required=True)  # Ex: Classique, Day Use, Flexible
    code = fields.Selection(
        [
            ("classic", "Classique (nuitée)"),
            ("day_use", "Day Use"),
            ("flexible", "Flexible"),
        ],
        required=True,
        string="Code",
    )

    checkin_time = fields.Float(
        string="Heure de check-in (si fixe)",
        help="Exemple : 14.5 = 14h30 Format décimal (ex: 14.5 = 14h30)"
    )
    checkout_time = fields.Float(
        string="Heure de check-out (si fixe)",
        help="Exemple : 11.0 = 11h00"
    )
    is_flexible = fields.Boolean(string="Heures flexibles", default=False)
    active = fields.Boolean(default=True)
    description = fields.Text("Description", help="Description du type de réservation")
