# -*- coding: utf-8 -*-
# from odoo import http


# class PurchaseSequentialApproval(http.Controller):
#     @http.route('/purchase_sequential_approval/purchase_sequential_approval', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/purchase_sequential_approval/purchase_sequential_approval/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('purchase_sequential_approval.listing', {
#             'root': '/purchase_sequential_approval/purchase_sequential_approval',
#             'objects': http.request.env['purchase_sequential_approval.purchase_sequential_approval'].search([]),
#         })

#     @http.route('/purchase_sequential_approval/purchase_sequential_approval/objects/<model("purchase_sequential_approval.purchase_sequential_approval"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('purchase_sequential_approval.object', {
#             'object': obj
#         })

