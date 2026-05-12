# -*- coding: utf-8 -*-
# from odoo import http


# class DslQuotationInvoiceMining(http.Controller):
#     @http.route('/dsl_quotation_invoice_mining/dsl_quotation_invoice_mining', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dsl_quotation_invoice_mining/dsl_quotation_invoice_mining/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dsl_quotation_invoice_mining.listing', {
#             'root': '/dsl_quotation_invoice_mining/dsl_quotation_invoice_mining',
#             'objects': http.request.env['dsl_quotation_invoice_mining.dsl_quotation_invoice_mining'].search([]),
#         })

#     @http.route('/dsl_quotation_invoice_mining/dsl_quotation_invoice_mining/objects/<model("dsl_quotation_invoice_mining.dsl_quotation_invoice_mining"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dsl_quotation_invoice_mining.object', {
#             'object': obj
#         })

