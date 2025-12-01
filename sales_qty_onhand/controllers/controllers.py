# -*- coding: utf-8 -*-
# from odoo import http


# class SalesQtyOnhand(http.Controller):
#     @http.route('/sales_qty_onhand/sales_qty_onhand', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sales_qty_onhand/sales_qty_onhand/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sales_qty_onhand.listing', {
#             'root': '/sales_qty_onhand/sales_qty_onhand',
#             'objects': http.request.env['sales_qty_onhand.sales_qty_onhand'].search([]),
#         })

#     @http.route('/sales_qty_onhand/sales_qty_onhand/objects/<model("sales_qty_onhand.sales_qty_onhand"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sales_qty_onhand.object', {
#             'object': obj
#         })

