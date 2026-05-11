# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class dcl_approval_request_pdf(models.Model):
#     _name = 'dcl_approval_request_pdf.dcl_approval_request_pdf'
#     _description = 'dcl_approval_request_pdf.dcl_approval_request_pdf'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

