# -*- coding: utf-8 -*-
# from odoo import http


# class FieldSalesVisit(http.Controller):
#     @http.route('/field_sales_visit/field_sales_visit', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/field_sales_visit/field_sales_visit/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('field_sales_visit.listing', {
#             'root': '/field_sales_visit/field_sales_visit',
#             'objects': http.request.env['field_sales_visit.field_sales_visit'].search([]),
#         })

#     @http.route('/field_sales_visit/field_sales_visit/objects/<model("field_sales_visit.field_sales_visit"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('field_sales_visit.object', {
#             'object': obj
#         })

