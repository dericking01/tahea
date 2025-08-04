# -*- coding: utf-8 -*-
# from odoo import http


# class Auction(http.Controller):
#     @http.route('/auction/auction', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/auction/auction/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('auction.listing', {
#             'root': '/auction/auction',
#             'objects': http.request.env['auction.auction'].search([]),
#         })

#     @http.route('/auction/auction/objects/<model("auction.auction"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('auction.object', {
#             'object': obj
#         })

