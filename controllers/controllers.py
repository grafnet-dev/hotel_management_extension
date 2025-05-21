# -*- coding: utf-8 -*-
# from odoo import http


# class HotelManagementExtension(http.Controller):
#     @http.route('/hotel_management_extension/hotel_management_extension', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hotel_management_extension/hotel_management_extension/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hotel_management_extension.listing', {
#             'root': '/hotel_management_extension/hotel_management_extension',
#             'objects': http.request.env['hotel_management_extension.hotel_management_extension'].search([]),
#         })

#     @http.route('/hotel_management_extension/hotel_management_extension/objects/<model("hotel_management_extension.hotel_management_extension"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hotel_management_extension.object', {
#             'object': obj
#         })

