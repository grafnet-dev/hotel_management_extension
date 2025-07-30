from odoo import models, fields
# ===============================
# HOTEL POS MENU LINE (LES LIGNES)
# ===============================
class HotelPOSMenuLine(models.Model):
    _name = 'hotel.pos.menu.line'
    _description = 'Ligne de menu POS hôtelier'

    menu_id = fields.Many2one('hotel.pos.menu', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True, string="Produit")

    display_name = fields.Char(string="Nom affiché", help="Nom visible dans le menu POS")
    category_label = fields.Char(string="Catégorie visuelle", help="Ex : Boissons, Plats, Desserts")
    price_override = fields.Float(string="Prix personnalisé (optionnel)")