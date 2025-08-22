from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class RoomBooking(models.Model):
    _inherit = 'room.booking'
    
    stay_ids = fields.One2many(
        'hotel.booking.stay',  
        'booking_id',
        string="Séjours",
        help="Séjours individuels liés à cette réservation"
    )


    def action_start_checkin_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fiche de Police',
            'res_model': 'hotel.police.form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
            }
        }

    def action_view_booking_stays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Séjours liés',
            'res_model': 'hotel.booking.stay',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id},
        }
