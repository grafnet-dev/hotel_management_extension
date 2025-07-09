# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HotelRoomType(models.Model):
    _name = 'hotel.room.type'
    _description = 'Room Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nom du type', required=True, translate=True)
    short_description = fields.Char(string='Résumé', translate=True)
    description = fields.Html(string='Description', translate=True)
    price = fields.Float(string='Prix par nuit')
    currency_id = fields.Many2one(
        'res.currency', 
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    capacity = fields.Integer(string='Capacité max')
    bed_type = fields.Selection([
        ('single', 'Lit simple'),
        ('double', 'Lit double'),
        ('queen', 'Queen size'),
        ('king', 'King size'),
    ], string='Type de lit')
    image_ids = fields.One2many(
        'hotel.room.type.image',
        'room_type_id',
        string="Images"
    )
    amenities_ids = fields.Many2many(
        'hotel.amenity',
        string='Équipements'
    )
    active = fields.Boolean(default=True)
    room_ids = fields.One2many(
        'hotel.room',
        'room_type_id',
        string='Chambres liées'
    )

    available_count = fields.Integer(
        string="Chambres disponibles",
        compute="_compute_available_count"
    )

    @api.depends('room_ids.status')
    def _compute_available_count(self):
        for rec in self:
            rec.available_count = len(rec.room_ids.filtered(lambda r: r.status == 'available'))
