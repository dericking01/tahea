# -*- coding: utf-8 -*-
# from odoo import http


# class GwambinaApprovalBillControl(http.Controller):
#     @http.route('/gwambina_approval_bill_control/gwambina_approval_bill_control', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gwambina_approval_bill_control/gwambina_approval_bill_control/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('gwambina_approval_bill_control.listing', {
#             'root': '/gwambina_approval_bill_control/gwambina_approval_bill_control',
#             'objects': http.request.env['gwambina_approval_bill_control.gwambina_approval_bill_control'].search([]),
#         })

#     @http.route('/gwambina_approval_bill_control/gwambina_approval_bill_control/objects/<model("gwambina_approval_bill_control.gwambina_approval_bill_control"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gwambina_approval_bill_control.object', {
#             'object': obj
#         })

