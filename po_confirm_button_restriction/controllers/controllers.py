# -*- coding: utf-8 -*-
# from odoo import http


# class PoConfirmButtonRestriction(http.Controller):
#     @http.route('/po_confirm_button_restriction/po_confirm_button_restriction', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/po_confirm_button_restriction/po_confirm_button_restriction/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('po_confirm_button_restriction.listing', {
#             'root': '/po_confirm_button_restriction/po_confirm_button_restriction',
#             'objects': http.request.env['po_confirm_button_restriction.po_confirm_button_restriction'].search([]),
#         })

#     @http.route('/po_confirm_button_restriction/po_confirm_button_restriction/objects/<model("po_confirm_button_restriction.po_confirm_button_restriction"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('po_confirm_button_restriction.object', {
#             'object': obj
#         })

