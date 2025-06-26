from odoo import models, fields

class FoodBookingLine(models.Model):
   _inherit = "food.booking.line"

food_id = fields.Many2one('product.product', string="Product",
                              help="Indicates the Food Product")
  
