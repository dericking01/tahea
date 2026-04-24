from odoo import models, fields, api

class ApprovalRequestBillLine(models.Model):
    _name = 'approval.request.bill.line'
    _description = 'Approval Request Bill Line'

    approval_request_id = fields.Many2one('approval.request', string="Approval Request", ondelete='cascade')

    bill_id = fields.Many2one(
        'account.move',
        string="Vendor Bill",
        domain=[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])],
        required=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Vendor",
        related='bill_id.partner_id',
        store=True,
        readonly=True
    )

    bill_amount = fields.Monetary(
        string="Bill Amount",
        related='bill_id.amount_total',
        store=True,
        readonly=True
    )

    amount_to_pay = fields.Monetary(
        string="Planned To Pay",
        required=True
    )

    currency_id = fields.Many2one(
        related='approval_request_id.currency_id',
        store=True,
        readonly=True
    )

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    bill_line_ids = fields.One2many(
        'approval.request.bill.line',
        'approval_request_id',
        string="Bills"
    )

    total_bill_amount = fields.Monetary(
        string="Total Bill Amount",
        compute='_compute_total_bill_amount',
        currency_field='currency_id'
    )

    total_to_pay = fields.Monetary(
        string="Total To Pay",
        compute='_compute_total_to_pay',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('bill_line_ids.bill_amount')
    def _compute_total_bill_amount(self):
        for rec in self:
            rec.total_bill_amount = sum(rec.bill_line_ids.mapped('bill_amount'))

    @api.depends('bill_line_ids.amount_to_pay')
    def _compute_total_to_pay(self):
        for rec in self:
            rec.total_to_pay = sum(rec.bill_line_ids.mapped('amount_to_pay'))