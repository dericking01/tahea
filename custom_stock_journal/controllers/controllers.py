# -*- coding: utf-8 -*-
# from odoo import http


# class CustomStockJournal(http.Controller):
#     @http.route('/custom_stock_journal/custom_stock_journal', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_stock_journal/custom_stock_journal/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_stock_journal.listing', {
#             'root': '/custom_stock_journal/custom_stock_journal',
#             'objects': http.request.env['custom_stock_journal.custom_stock_journal'].search([]),
#         })

#     @http.route('/custom_stock_journal/custom_stock_journal/objects/<model("custom_stock_journal.custom_stock_journal"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_stock_journal.object', {
#             'object': obj
#         })

