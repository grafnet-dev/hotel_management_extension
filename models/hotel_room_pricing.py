from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api

class HotelRoomPricing(models.Model):
    _name = "hotel.room.pricing"
    _description = "Tarification par type de réservation pour les chambres"

    room_id = fields.Many2one("hotel.room", required=True, ondelete="cascade")
    reservation_type_id = fields.Many2one("hotel.reservation.type", required=True)

    price = fields.Float("Prix (Fixe ou base)", digits="Product Price")

    # Si c'est un type flexible, permettre un tarif horaire
    hourly_price = fields.Float("Tarif horaire", digits="Product Price")
    is_hourly_based = fields.Boolean(
        string="Tarif horaire actif",
        compute="_compute_is_hourly_based",
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency', required=False, default=lambda self: self.env.company.currency_id
    )

    @api.depends('reservation_type_id')
    def _compute_is_hourly_based(self):
        for rec in self:
            rec.is_hourly_based = rec.reservation_type_id.is_flexible

    _sql_constraints = [
        ('unique_room_type', 'unique(room_id, reservation_type_id)', 'Un tarif existe déjà pour cette chambre et ce type.')
    ]
