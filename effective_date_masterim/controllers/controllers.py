# -*- coding: utf-8 -*-
# from odoo import http


# class EffectiveDateMasterim(http.Controller):
#     @http.route('/effective_date_masterim/effective_date_masterim', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/effective_date_masterim/effective_date_masterim/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('effective_date_masterim.listing', {
#             'root': '/effective_date_masterim/effective_date_masterim',
#             'objects': http.request.env['effective_date_masterim.effective_date_masterim'].search([]),
#         })

#     @http.route('/effective_date_masterim/effective_date_masterim/objects/<model("effective_date_masterim.effective_date_masterim"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('effective_date_masterim.object', {
#             'object': obj
#         })

