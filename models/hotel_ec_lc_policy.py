
from odoo import models, fields, api, _


class HotelPolicyRule(models.Model):
    _name = "hotel.eclc.policy"
    _description = "Règle de politique (Early / Late)"
    _order = "reservation_mode, rule_type, start_hour"

    room_type_id = fields.Many2one("hotel.room.type", string="Type de chambre", ondelete="cascade")
    
    reservation_mode = fields.Selection([
        ("overnight", "Nuitée"),
        ("dayuse", "Day-use"),
    ], required=True)

    rule_type = fields.Selection([
        ("early", "Early Check-in"),
        ("late", "Late Check-out"),
    ], required=True)

    start_hour = fields.Float(string="Heure début", required=True, help="Ex: 6.0 pour 06:00")
    end_hour = fields.Float(string="Heure fin", required=True, help="Ex: 11.99 pour 11:59")

    surcharge_percent = fields.Float(string="Supplément (%)", default=0.0)
    is_full_night = fields.Boolean(string="Facturation nuit complète", default=False)
    notes = fields.Text(string="Remarques")
