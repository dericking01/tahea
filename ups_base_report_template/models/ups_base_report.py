from odoo import api, fields, models

class InvoiceReport(models.Model):
    _name = "ups.base.report"
    _description = "ups Base Report"

    # ups_custom_report = fields.Boolean(string="Custom Report")
