# -*- coding: utf-8 -*-
# from odoo import http


# class ApprovalVendorBills(http.Controller):
#     @http.route('/approval_vendor_bills/approval_vendor_bills', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/approval_vendor_bills/approval_vendor_bills/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('approval_vendor_bills.listing', {
#             'root': '/approval_vendor_bills/approval_vendor_bills',
#             'objects': http.request.env['approval_vendor_bills.approval_vendor_bills'].search([]),
#         })

#     @http.route('/approval_vendor_bills/approval_vendor_bills/objects/<model("approval_vendor_bills.approval_vendor_bills"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('approval_vendor_bills.object', {
#             'object': obj
#         })

