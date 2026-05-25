# -*- coding: utf-8 -*-

from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    invoice_templates = fields.Selection(
        [('template1','Invoice Template 1'),
         ('template2','Invoice Template 2'),
         ('template3','Invoice Template 3'),
         ('template4','Invoice Template 4'),
         ('template5','Invoice Template 5'),
         ('template6','Invoice Template 6'),
         ('template7','Invoice Template 7'),
         ('template8','Invoice Template 8'), 
         ('template9','Invoice Template 9'),
         ('template10','Invoice Template 10'), 
         ])
    invoice_primary_color = fields.Char('Invoice Primary Color')
    invoice_secondary_color = fields.Char('Invoice Secondary Color')
    invoice_header_color = fields.Char('Invoice Header Color')
    invoice_watermark = fields.Binary(string='Invoice Watermark', help='Upload watermark image here')