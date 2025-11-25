from odoo import models, fields, api

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    vendor_bill_ids = fields.Many2many(
        'account.move',
        string="Vendor Bills",
        domain=[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])]
    )

    total_bill_amount = fields.Monetary(
        string="Total Amount",
        currency_field='currency_id',
        compute='_compute_total_bill_amount',
        store=False
    )

    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)

    @api.depends('vendor_bill_ids')
    def _compute_total_bill_amount(self):
        for rec in self:
            rec.total_bill_amount = sum(rec.vendor_bill_ids.mapped('amount_total'))
