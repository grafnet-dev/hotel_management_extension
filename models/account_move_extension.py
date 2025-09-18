from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    stay_id = fields.Many2one(
        "hotel.booking.stay",
        string="Séjour",
        ondelete="cascade",
        help="Séjour associé à cette facture"
    )
