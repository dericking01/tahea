# -*- coding: utf-8 -*-
# from odoo import http


# class MembersExt(http.Controller):
#     @http.route('/members_ext/members_ext', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/members_ext/members_ext/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('members_ext.listing', {
#             'root': '/members_ext/members_ext',
#             'objects': http.request.env['members_ext.members_ext'].search([]),
#         })

#     @http.route('/members_ext/members_ext/objects/<model("members_ext.members_ext"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('members_ext.object', {
#             'object': obj
#         })
