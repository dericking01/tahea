# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class field_sales_visit(models.Model):
#     _name = 'field_sales_visit.field_sales_visit'
#     _description = 'field_sales_visit.field_sales_visit'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

