# -*- coding: utf-8 -*-
# from odoo import http


# class VendorMandatoryFields2(http.Controller):
#     @http.route('/vendor_mandatory_fields2/vendor_mandatory_fields2', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/vendor_mandatory_fields2/vendor_mandatory_fields2/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('vendor_mandatory_fields2.listing', {
#             'root': '/vendor_mandatory_fields2/vendor_mandatory_fields2',
#             'objects': http.request.env['vendor_mandatory_fields2.vendor_mandatory_fields2'].search([]),
#         })

#     @http.route('/vendor_mandatory_fields2/vendor_mandatory_fields2/objects/<model("vendor_mandatory_fields2.vendor_mandatory_fields2"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('vendor_mandatory_fields2.object', {
#             'object': obj
#         })

