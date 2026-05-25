from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company)

    ups_custom_report = fields.Boolean(
        string="Custom Report",
        related='company_id.ups_custom_report',
        readonly=False
    )

