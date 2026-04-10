# -*- coding: utf-8 -*-
# from odoo import http


# class ApprovalMod(http.Controller):
#     @http.route('/approval_mod/approval_mod', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/approval_mod/approval_mod/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('approval_mod.listing', {
#             'root': '/approval_mod/approval_mod',
#             'objects': http.request.env['approval_mod.approval_mod'].search([]),
#         })

#     @http.route('/approval_mod/approval_mod/objects/<model("approval_mod.approval_mod"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('approval_mod.object', {
#             'object': obj
#         })
