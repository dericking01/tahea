# -*- coding: utf-8 -*-
# from odoo import http


# class ProductCategory(http.Controller):
#     @http.route('/product_category/product_category', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/product_category/product_category/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('product_category.listing', {
#             'root': '/product_category/product_category',
#             'objects': http.request.env['product_category.product_category'].search([]),
#         })

#     @http.route('/product_category/product_category/objects/<model("product_category.product_category"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('product_category.object', {
#             'object': obj
#         })

