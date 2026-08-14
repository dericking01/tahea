# -*- coding: utf-8 -*-
# from odoo import http


# class StockPickingJournalEntry(http.Controller):
#     @http.route('/stock_picking_journal_entry/stock_picking_journal_entry', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_picking_journal_entry/stock_picking_journal_entry/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_picking_journal_entry.listing', {
#             'root': '/stock_picking_journal_entry/stock_picking_journal_entry',
#             'objects': http.request.env['stock_picking_journal_entry.stock_picking_journal_entry'].search([]),
#         })

#     @http.route('/stock_picking_journal_entry/stock_picking_journal_entry/objects/<model("stock_picking_journal_entry.stock_picking_journal_entry"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_picking_journal_entry.object', {
#             'object': obj
#         })

