from odoo import models, fields

class HotelRoomTypeImage(models.Model):
    _name = 'hotel.room.type.image'
    _description = 'Images des types de chambres'

    room_type_id = fields.Many2one(
        'hotel.room.type',
        string="Type de chambre",
        required=True,
        ondelete='cascade'
    )
    image = fields.Image(
        string='Image',
        required=True,
        max_width=1920,
        max_height=1920
    )
    description = fields.Char(string='Légende / description')
