from odoo import models, fields

class HotelRoomImage(models.Model):
    _name = 'hotel.room.image'
    _description = 'Hotel Room Image'

    room_id = fields.Many2one('hotel.room', string="Room", required=True, ondelete="cascade")
    image = fields.Image(string="Image", required=True)
    description = fields.Char(string="Description")
#Crée un modèle hotel.room.image avec un champ sequence pour trier.
    #room_id = fields.Many2one('hotel.room', string="Room", required=True, ondelete="cascade")
    #image = fields.Image(string="Image", max_width=1920, max_height=1920, required=True)
    #description = fields.Char(string="Description")
    #sequence = fields.Integer(string="Sequence", default=10)