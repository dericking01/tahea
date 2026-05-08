from odoo import models, fields

class CashierReportLine(models.Model):
    _name = "cashier.report.line"
    _description = "Cashier Report Line"

    report_id = fields.Many2one('cashier.report', string="Report", ondelete="cascade")
    payment_method_id = fields.Many2one('cashier.payment.method', string="Payment Method", required=True)
    transaction_ref = fields.Char(string="Transaction Reference")
    amount = fields.Monetary(string="Amount")
    currency_id = fields.Many2one(related="report_id.currency_id", store=True, readonly=True)

class CashierPaymentMethod(models.Model):
    _name = "cashier.payment.method"
    _description = "Cashier Payment Method"

    name = fields.Char(string="Payment Method", required=True)
    code = fields.Char(string="Code")
    active = fields.Boolean(string="Active", default=True)
