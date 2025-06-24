from odoo import models

class RoomBooking(models.Model):
    _inherit = 'room.booking'

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
