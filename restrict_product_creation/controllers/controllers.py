# -*- coding: utf-8 -*-
# from odoo import http


# class RestrictProductCreation(http.Controller):
#     @http.route('/restrict_product_creation/restrict_product_creation', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/restrict_product_creation/restrict_product_creation/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('restrict_product_creation.listing', {
#             'root': '/restrict_product_creation/restrict_product_creation',
#             'objects': http.request.env['restrict_product_creation.restrict_product_creation'].search([]),
#         })

#     @http.route('/restrict_product_creation/restrict_product_creation/objects/<model("restrict_product_creation.restrict_product_creation"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('restrict_product_creation.object', {
#             'object': obj
#         })

