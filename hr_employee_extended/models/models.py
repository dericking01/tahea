# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class hr_employee_extended(models.Model):
#     _name = 'hr_employee_extended.hr_employee_extended'
#     _description = 'hr_employee_extended.hr_employee_extended'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
