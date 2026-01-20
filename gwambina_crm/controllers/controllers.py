# -*- coding: utf-8 -*-
# from odoo import http


# class GwambinaCrm(http.Controller):
#     @http.route('/gwambina_crm/gwambina_crm', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gwambina_crm/gwambina_crm/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('gwambina_crm.listing', {
#             'root': '/gwambina_crm/gwambina_crm',
#             'objects': http.request.env['gwambina_crm.gwambina_crm'].search([]),
#         })

#     @http.route('/gwambina_crm/gwambina_crm/objects/<model("gwambina_crm.gwambina_crm"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gwambina_crm.object', {
#             'object': obj
#         })

