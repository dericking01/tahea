# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class dsl_quotation_invoice_mining(models.Model):
#     _name = 'dsl_quotation_invoice_mining.dsl_quotation_invoice_mining'
#     _description = 'dsl_quotation_invoice_mining.dsl_quotation_invoice_mining'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

