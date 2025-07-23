from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    hotel_product_type = fields.Selection([
        ('meal', 'Plat'),
        ('drink', 'Boisson'),
        ('dessert', 'Dessert'),
        ('ingredient', 'Ingrédient'),
        ('service', 'Service'),
        ('food', 'Food'),
    ], string="Type de produit hôtelier")

    is_available_restaurant = fields.Boolean(string="Dispo. Restaurant", default=False)
    is_available_room_service = fields.Boolean(string="Dispo. Room Service", default=False)
    is_available_minibar = fields.Boolean(string="Dispo. Minibar", default=False)

    kitchen_note = fields.Text(string="Note cuisine (si applicable)")