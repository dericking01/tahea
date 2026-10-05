# -*- coding: utf-8 -*-
# from odoo import http


# class PosOrderAnalysis(http.Controller):
#     @http.route('/pos_order_analysis/pos_order_analysis', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pos_order_analysis/pos_order_analysis/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pos_order_analysis.listing', {
#             'root': '/pos_order_analysis/pos_order_analysis',
#             'objects': http.request.env['pos_order_analysis.pos_order_analysis'].search([]),
#         })

#     @http.route('/pos_order_analysis/pos_order_analysis/objects/<model("pos_order_analysis.pos_order_analysis"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pos_order_analysis.object', {
#             'object': obj
#         })
