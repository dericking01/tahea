# -*- coding: utf-8 -*-
# from odoo import http


# class FleetFuelManagement(http.Controller):
#     @http.route('/fleet_fuel_management/fleet_fuel_management', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fleet_fuel_management/fleet_fuel_management/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fleet_fuel_management.listing', {
#             'root': '/fleet_fuel_management/fleet_fuel_management',
#             'objects': http.request.env['fleet_fuel_management.fleet_fuel_management'].search([]),
#         })

#     @http.route('/fleet_fuel_management/fleet_fuel_management/objects/<model("fleet_fuel_management.fleet_fuel_management"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fleet_fuel_management.object', {
#             'object': obj
#         })

