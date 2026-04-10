# -*- coding: utf-8 -*-
# from odoo import http


# class Pharmacy(http.Controller):
#     @http.route('/pharmacy/pharmacy', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pharmacy/pharmacy/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pharmacy.listing', {
#             'root': '/pharmacy/pharmacy',
#             'objects': http.request.env['pharmacy.pharmacy'].search([]),
#         })

#     @http.route('/pharmacy/pharmacy/objects/<model("pharmacy.pharmacy"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pharmacy.object', {
#             'object': obj
#         })
