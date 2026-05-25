# -*- coding: utf-8 -*-

from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Related to res.company fields
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
        ],
        string="Template",
        related='company_id.invoice_templates',
        readonly=False
    )
    invoice_primary_color = fields.Char(
        string='Invoice Primary Color',
        related='company_id.invoice_primary_color',
        readonly=False
    )
    invoice_secondary_color = fields.Char(
        string='Invoice Secondary Color',
        related='company_id.invoice_secondary_color',
        readonly=False
    )
    invoice_header_color = fields.Char(
        string= 'Invoice Header Color',
        related='company_id.invoice_header_color',
        readonly=False)

    invoice_watermark = fields.Binary(
        string='Invoice Watermark',
        related='company_id.invoice_watermark',
        readonly=False
    )
    

    def invoice_reset_template_colors(self):
        for inv in self:
            inv.company_id.write({
                'invoice_primary_color': "",
                'invoice_secondary_color': "",
                'invoice_header_color': "",
            })
    