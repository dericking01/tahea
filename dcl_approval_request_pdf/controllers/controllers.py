# -*- coding: utf-8 -*-
# from odoo import http


# class DclApprovalRequestPdf(http.Controller):
#     @http.route('/dcl_approval_request_pdf/dcl_approval_request_pdf', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dcl_approval_request_pdf/dcl_approval_request_pdf/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dcl_approval_request_pdf.listing', {
#             'root': '/dcl_approval_request_pdf/dcl_approval_request_pdf',
#             'objects': http.request.env['dcl_approval_request_pdf.dcl_approval_request_pdf'].search([]),
#         })

#     @http.route('/dcl_approval_request_pdf/dcl_approval_request_pdf/objects/<model("dcl_approval_request_pdf.dcl_approval_request_pdf"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dcl_approval_request_pdf.object', {
#             'object': obj
#         })

