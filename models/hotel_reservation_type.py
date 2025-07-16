from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api



class HotelReservationType(models.Model):
    _name = "hotel.reservation.type"
    _description = "Type de réservation"

    room_type_id = fields.Many2one('hotel.room.type', string="Type de Chambre", required=True, ondelete="cascade")
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

    #checkin_time = fields.Float(string="Heure de check-in (si fixe)",help="Exemple : 14.5 = 14h30 Format décimal (ex: 14.5 = 14h30)")
    #checkout_time = fields.Float( string="Heure de check-out (si fixe)", help="Exemple : 11.0 = 11h00")
  
    
    
    #@api.constrains('is_flexible', 'checkin_time', 'checkout_time')
    #def _check_flexible_hours(self):
    #    for record in self:
    #       if record.is_flexible and (record.checkin_time or record.checkout_time):
    #           raise ValidationError("Les horaires ne doivent pas être définis pour un type flexible.")