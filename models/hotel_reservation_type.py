from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api



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
    
    is_flexible = fields.Boolean(string="Heures flexibles", default=False)
    active = fields.Boolean(default=True)
    description = fields.Text("Description", help="Description du type de réservation")

   