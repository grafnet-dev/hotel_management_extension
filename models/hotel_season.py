from odoo import models, fields, api


class HotelSeason(models.Model):
    _name = "hotel.season"
    _description = "Hotel Season"
    _order = "priority desc, date_start asc"

    name = fields.Char(string="Season Name", required=True)
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    priority = fields.Integer(
        string="Priority",
        default=10,
        help="Higher priority seasons will override lower ones if overlapping."
    )
    active = fields.Boolean(default=True)

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for season in self:
            if season.date_start > season.date_end:
                raise ValueError("Start date cannot be after end date.")


