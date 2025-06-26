from odoo import models, fields

# =======================
# HOTEL POS MENU (POS ID)
# =======================
class HotelPOSMenu(models.Model):
    _name = 'hotel.pos.menu'
    _description = 'Menu d’un point de vente hôtelier'

    name = fields.Char(required=True)
    pos_type = fields.Selection([
        ('restaurant', 'Restaurant'),
        ('room_service', 'Room Service'),
        ('minibar', 'Minibar'),
    ], required=True, string="Type de POS")

    line_ids = fields.One2many('hotel.pos.menu.line', 'menu_id', string="Lignes de menu")
