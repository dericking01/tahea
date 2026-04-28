from odoo import models, fields, api
from odoo.exceptions import ValidationError


# -------------------------------
# Line Model
# -------------------------------
class ApprovalRequestBillLine(models.Model):
    _name = 'approval.request.bill.line'
    _description = 'Approval Request Bill Line'

    approval_request_id = fields.Many2one(
        'approval.request',
        string="Approval Request",
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Vendor",
        domain=[('supplier_rank', '>', 0)],
        required=True
    )

    vendor_bill_ids = fields.Many2many(
        'account.move',
        string="Bills",
        domain="[('move_type','=','in_invoice'),"
               "('state','=','posted'),"
               "('payment_state','in',['not_paid','partial']),"
               "('partner_id','=',partner_id)]"
    )

    total_bill_amount = fields.Monetary(
        string="Total Bill Amount",
        compute='_compute_total_bill_amount',
        currency_field='currency_id'
    )

    planned_amount = fields.Monetary(
        string="Planned Amount To Pay",
        required=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='approval_request_id.currency_id',
        store=True,
        readonly=True
    )

    # -------------------------------
    # Compute total bill amount
    # -------------------------------
    @api.depends('vendor_bill_ids')
    def _compute_total_bill_amount(self):
        for rec in self:
            rec.total_bill_amount = sum(rec.vendor_bill_ids.mapped('amount_total'))

    # -------------------------------
    # Auto-fill planned amount
    # -------------------------------
    @api.onchange('vendor_bill_ids')
    def _onchange_vendor_bill_ids(self):
        for rec in self:
            rec.planned_amount = sum(rec.vendor_bill_ids.mapped('amount_residual'))

    # -------------------------------
    # Clear bills when vendor changes
    # -------------------------------
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.vendor_bill_ids = [(5, 0, 0)]

    # -------------------------------
    # Validation
    # -------------------------------
    @api.constrains('planned_amount', 'vendor_bill_ids')
    def _check_planned_amount(self):
        for rec in self:
            total_residual = sum(rec.vendor_bill_ids.mapped('amount_residual'))
            if rec.planned_amount > total_residual:
                raise ValidationError(
                    "Planned amount cannot exceed total residual amount."
                )


# -------------------------------
# Main Model Inherit
# -------------------------------
class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    bill_line_ids = fields.One2many(
        'approval.request.bill.line',
        'approval_request_id',
        string="Vendor Bills"
    )

    total_bill_amount = fields.Monetary(
        string="Total Amount Due",
        compute='_compute_total_all',
        currency_field='currency_id'
    )
    total_planned_amount = fields.Monetary(
    string="Total Planned Amount To Pay",
    compute='_compute_total_planned_amount',
    currency_field='currency_id')

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # -------------------------------
    # Compute grand total
    # -------------------------------
    @api.depends('bill_line_ids.total_bill_amount')
    def _compute_total_all(self):
        for rec in self:
            rec.total_bill_amount = sum(
                rec.bill_line_ids.mapped('total_bill_amount')
            )

    @api.depends('bill_line_ids.planned_amount')
    def _compute_total_planned_amount(self):
        for rec in self:
            rec.total_planned_amount = sum(
                rec.bill_line_ids.mapped('planned_amount')
            )

    # -------------------------------
    # Prevent duplicate bills
    # -------------------------------
    @api.constrains('bill_line_ids')
    def _check_duplicate_bills(self):
        for rec in self:
            all_bills = []
            for line in rec.bill_line_ids:
                for bill in line.vendor_bill_ids:
                    if bill in all_bills:
                        raise ValidationError(
                            "You cannot select the same bill more than once."
                        )
                    all_bills.append(bill)