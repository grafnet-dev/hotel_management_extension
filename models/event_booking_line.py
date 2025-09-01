from odoo import api, fields, models

class EventBookingLine(models.Model):
    _inherit = "event.booking.line"

    stay_id = fields.Many2one(
        "hotel.booking.stay", string="Séjour associé", required=True, ondelete="cascade"
    )

    booking_id = fields.Many2one("room.booking", deprecated=True)

    currency_id = fields.Many2one(
        related="stay_id.currency_id", string="Currency", store=True, readonly=True
    )
    state = fields.Selection(
        related="stay_id.state", string="Order Status", store=True, readonly=True
    )

  