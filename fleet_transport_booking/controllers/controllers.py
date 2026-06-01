# -*- coding: utf-8 -*-
# from odoo import http


# class FleetTransportBooking(http.Controller):
#     @http.route('/fleet_transport_booking/fleet_transport_booking', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fleet_transport_booking/fleet_transport_booking/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fleet_transport_booking.listing', {
#             'root': '/fleet_transport_booking/fleet_transport_booking',
#             'objects': http.request.env['fleet_transport_booking.fleet_transport_booking'].search([]),
#         })

#     @http.route('/fleet_transport_booking/fleet_transport_booking/objects/<model("fleet_transport_booking.fleet_transport_booking"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fleet_transport_booking.object', {
#             'object': obj
#         })

