# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    templates = fields.Selection(
        [('template1','Template 1'),
         ('template2','Template 2'),
         ('template3','Template 3'),
         ('template4','Template 4'),
         ('template5','Template 5'),
         ('template6','Template 6'),
         ('template7','Template 7'),
         ('template8','Template 8'),
         ('template9','Template 9'),
         ('template10','Template 10'),

         ])
    report_primary_color = fields.Char('Primary Color')
    report_secondary_color = fields.Char('Secondary Color')
    report_header_color = fields.Char('Header Color')
    watermark = fields.Binary(string='Watermark', help='Upload watermark image here')
    report_background = fields.Binary(string="background img")