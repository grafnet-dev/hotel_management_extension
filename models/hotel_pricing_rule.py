from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
        default=lambda self: self.env.company.currency_id,
    )

    active = fields.Boolean(default=True)

    # Prix simple pour réservation non flexible
    price = fields.Float(
        string="Base Price", required=True, help="Price applied for this combination."
    )

    line_ids = fields.One2many(
        "hotel.pricing.rule.line",
        "rule_id",
        string="Pricing Lines",
    )
    
    is_flexible = fields.Boolean(
        related="reservation_type_id.is_flexible",
        store=True,
        readonly=True,
    )

    @api.constrains("price", "line_ids", "is_flexible")
    def _check_price_rules(self):
        for rule in self:
            if rule.is_flexible and not rule.line_ids:
                raise ValidationError(
                    "Les réservations flexibles doivent avoir des lignes de tarification (durée min/max)."
                )
            if not rule.is_flexible and not rule.price:
                raise ValidationError(
                    "Les réservations non flexibles doivent avoir un prix fixe."
                )


class HotelPricingRuleLine(models.Model):
    _name = "hotel.pricing.rule.line"
    _description = "Hotel Pricing Rule Line"
    _order = "min_duration"

    rule_id = fields.Many2one(
        "hotel.pricing.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
    )

    min_duration = fields.Float(
        string="Durée min (heures)",
        help="Durée minimale (en heures) pour appliquer cette tarification",
    )

    max_duration = fields.Float(
        string="Durée max (heures)",
        help="Durée maximale (en heures) pour appliquer cette tarification. Vide = illimité.",
    )

    price = fields.Float(
        string="Prix",
        required=True,
    )

    currency_id = fields.Many2one(
        related="rule_id.currency_id",
        store=True,
        readonly=True,
    )
