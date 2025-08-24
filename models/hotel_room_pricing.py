from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HotelRoomPricing(models.Model):
    _name = "hotel.room.pricing"
    _description = "Tarification par type de chambre et réservation"
    _order = "room_type_id, reservation_type_id"

    room_type_id = fields.Many2one(
        "hotel.room.type",
        string="Type de chambre",
        required=True,
        ondelete="cascade"
    )

    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        required=True,
        ondelete="cascade"
    )
    
    currency_id = fields.Many2one(
    'res.currency',
    string="Devise",
    default=lambda self: self.env.company.currency_id.id,
    required=True
    )


    pricing_mode = fields.Selection([
        ("fixed", "Prix fixe"),
        ("percentage", "Pourcentage du prix de base"),
        ("hourly", "Tarif horaire"),
    ], string="Mode tarifaire", required=True)

    price_value = fields.Float(
        string="Valeur",
        required=True,
        help="Si mode = fixe → montant, "
             "si mode = percentage → pourcentage (%), "
             "si mode = hourly → prix par heure."
    )

    min_hours = fields.Float(
        string="Durée minimale (h)",
        default=1.0,
        help="Applicable uniquement si mode horaire."
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_tariff_per_type",
            "unique(room_type_id, reservation_type_id, pricing_mode)",
            "Une règle de tarification existe déjà pour ce couple chambre + type de réservation + mode."
        )
    ]

    # -------------------
    # MÉTHODE DE CALCUL
    # -------------------
    def compute_price(self, base_price, duration_hours=None):
        """Calcule le prix selon la règle tarifaire"""
        self.ensure_one()

        if self.pricing_mode == "fixed":
            return self.price_value

        elif self.pricing_mode == "percentage":
            return base_price * (self.price_value / 100.0)

        elif self.pricing_mode == "hourly":
            if not duration_hours:
                raise ValidationError("La durée est requise pour une tarification horaire.")
            hours = max(duration_hours, self.min_hours)
            return hours * self.price_value

        return base_price
