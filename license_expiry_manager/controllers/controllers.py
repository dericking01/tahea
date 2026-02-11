# -*- coding: utf-8 -*-
# from odoo import http


# class LicenseExpiryManager(http.Controller):
#     @http.route('/license_expiry_manager/license_expiry_manager', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/license_expiry_manager/license_expiry_manager/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('license_expiry_manager.listing', {
#             'root': '/license_expiry_manager/license_expiry_manager',
#             'objects': http.request.env['license_expiry_manager.license_expiry_manager'].search([]),
#         })

#     @http.route('/license_expiry_manager/license_expiry_manager/objects/<model("license_expiry_manager.license_expiry_manager"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('license_expiry_manager.object', {
#             'object': obj
#         })

