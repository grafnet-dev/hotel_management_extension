from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class RoomBookingLine(models.Model):
    _inherit = "room.booking.line"

    reservation_type_id = fields.Many2one(
        'hotel.reservation.type',
        string="Type de réservation",
        required=False,
        domain="[('id', 'in', room_id.reservation_type_ids)]",
        help="Définit si la réservation est classique, day use ou flexible."
    )

   
