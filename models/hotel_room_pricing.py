from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api

class HotelRoomPricing(models.Model):
    _name = "hotel.room.pricing"
    _description = "Tarification par type de réservation pour les chambres"

    room_id = fields.Many2one("hotel.room", required=False, ondelete="cascade")
    room_type_id = fields.Many2one('hotel.room.type', string="Type de Chambre", required=True, ondelete="cascade")
    reservation_type_id = fields.Many2one("hotel.reservation.type", required=True)
    # Prix fixe pour les types classiques (nuitée, day-use)
    price = fields.Float("Prix (Fixe ou base)", digits="Product Price")
    # Dans hotel.room.pricing, ajoutez temporairement :
    hourly_price = fields.Float(string="Hourly Price (DEPRECATED)", digits="Product Price")

    # Tarification horaire (activée si le type de réservation est flexible)
    is_hourly_based = fields.Boolean(
        string="Tarif horaire actif",
        compute="_compute_is_hourly_based",
        store=True
    )
    # Tarification par bloc (ex : 60€ les 6h)
    price_per_block = fields.Float(
        string="Prix par tranche",
        digits="Product Price",
        help="Tarif fixe pour une tranche définie (ex: 60€ les 6h)"
    )
    block_duration = fields.Float(
        string="Durée d’un bloc (h)",
        help="Durée couverte par la tranche tarifaire (ex: 6h)"
    )
    # Majoration si réservation inclut des heures de nuit (22h–6h)
    night_extra_percent = fields.Float(
        string="Majoration de nuit (%)",
        default=0.0,
        help="Pourcentage à appliquer si la réservation couvre des heures entre 22h et 6h"
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
#Gérer des promotions, ex : early check-in gratuit si 2 nuits réservées

#Automatiser selon la disponibilité réelle des chambres