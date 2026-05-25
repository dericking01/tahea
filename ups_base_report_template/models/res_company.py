from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    ups_custom_report = fields.Boolean(
        string="Custom Report"
    )

    