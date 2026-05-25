# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Related to res.company fields
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
        ('template10','Template 10'),],
        string="Template",
        related='company_id.templates',
        readonly=False
    )
    report_primary_color = fields.Char(
        string='Primary Color',
        related='company_id.report_primary_color',
        readonly=False
    )
    report_secondary_color = fields.Char(
        string='Secondary Color',
        related='company_id.report_secondary_color',
        readonly=False
    )
    report_header_color = fields.Char(
        string= 'Header Color',
        related='company_id.report_header_color',
        readonly=False)

    watermark = fields.Binary(
        string='Watermark',
        related='company_id.watermark',
        readonly=False
    )
    report_background = fields.Binary(related='company_id.report_background',string="background img",readonly=False)
    

    def reset_template_colors(self):
        for wiz in self:
            wiz.company_id.write({
                'report_primary_color': "",
                'report_secondary_color': "",
                'report_header_color': "",
            })
    