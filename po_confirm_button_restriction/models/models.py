# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class po_confirm_button_restriction(models.Model):
#     _name = 'po_confirm_button_restriction.po_confirm_button_restriction'
#     _description = 'po_confirm_button_restriction.po_confirm_button_restriction'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

