# -*- coding: utf-8 -*-
# from odoo import http


# class AprovalBill(http.Controller):
#     @http.route('/aproval_bill/aproval_bill', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/aproval_bill/aproval_bill/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('aproval_bill.listing', {
#             'root': '/aproval_bill/aproval_bill',
#             'objects': http.request.env['aproval_bill.aproval_bill'].search([]),
#         })

#     @http.route('/aproval_bill/aproval_bill/objects/<model("aproval_bill.aproval_bill"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('aproval_bill.object', {
#             'object': obj
#         })

