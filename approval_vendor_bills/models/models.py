# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class approval_vendor_bills(models.Model):
#     _name = 'approval_vendor_bills.approval_vendor_bills'
#     _description = 'approval_vendor_bills.approval_vendor_bills'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

