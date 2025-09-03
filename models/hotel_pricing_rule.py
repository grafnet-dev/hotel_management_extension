from odoo import models, fields, api


class HotelPricingRule(models.Model):
    _name = "hotel.pricing.rule"
    _description = "Hotel Pricing Rule"
    _order = "room_type_id, reservation_type_id, season_id"

    room_type_id = fields.Many2one(
        "hotel.room.type",
        string="Room Type",
        required=True,
    )
    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Reservation Type",
        required=True,
    )
    season_id = fields.Many2one(
        "hotel.season",
        string="Season",
        help="If empty, this rule applies as a default (no season restriction).",
    )
    price = fields.Float(
        string="Base Price", required=True, help="Price applied for this combination."
    )
    unit = fields.Selection(
        [
            ("night", "Par nuit"),
            ("hour", "Par heure"),
            ("slot", "Forfait / slot"),
        ],
        default="night",
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=False,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)
