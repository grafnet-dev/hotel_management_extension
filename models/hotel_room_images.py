from odoo import models, fields

class HotelRoomImage(models.Model):
    _name = "hotel.room.image"
    _description = "Room Images"

    room_id = fields.Many2one("hotel.room", required=True, ondelete="cascade")
    image = fields.Image(string="Image", required=True)
    description = fields.Char(string="Description")
