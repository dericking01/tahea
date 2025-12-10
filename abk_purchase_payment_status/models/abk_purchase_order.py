"""
Module to extend purchase order functionality with payment status tracking.
"""

from odoo import models, fields, api


class PurchaseOrder(models.Model):
    """
    Extends the purchase.order model to include payment status and amount paid tracking.
    """
    _inherit = 'purchase.order'

    abk_payment_status = fields.Selection(
        [
            ('not_paid', 'Not Paid'),
            ('partial_paid', 'Partial Paid'),
            ('fully_paid', 'Fully Paid'),
            ('nothing', 'Bill Not Created')
        ],
        string="Payment Status",
        compute="_compute_payment_status",
        copy=False,
        store=True,
        readonly=True,
        default="not_paid"
    )

    @api.depends('invoice_ids.payment_state', 'invoice_ids.amount_residual')
    def _compute_payment_status(self):
        """
        Compute the payment status based on related invoices' payment states.
        """
        for rec in self:
            if rec.invoice_ids:
                full_paid = 0
                partial_paid = 0
                no_paid = 0
                for lines in rec.invoice_ids:
                    if lines.amount_residual == 0.0:
                        full_paid += 1
                    elif lines.amount_residual < lines.amount_total and lines.amount_residual > 0:
                        partial_paid += 1
                    else:
                        no_paid += 1
                if full_paid > 0 and partial_paid == 0 and no_paid == 0:
                    rec.abk_payment_status = 'fully_paid'
                elif full_paid > 0 or (full_paid == 0 and partial_paid > 0):
                    rec.abk_payment_status = 'partial_paid'
                else:
                    rec.abk_payment_status = 'not_paid'
            else:
                rec.abk_payment_status = 'nothing'

    abk_amount_paid = fields.Float(
        compute='_compute_abk_amount_paid',
        string="Amount Paid",
        copy=False
    )

    @api.depends('invoice_ids', 'abk_payment_status', 'invoice_status')
    def _compute_abk_amount_paid(self):
        """
        Compute the total amount paid based on posted invoices and their payment states.
        """
        for order in self:
            order.abk_amount_paid = 0.0
            for invoice in order.invoice_ids:
                if (invoice.state == 'posted' and
                    invoice.move_type == 'in_invoice' and
                    invoice.payment_state in ('in_payment', 'paid', 'partial', 'reversed')):
                    order.abk_amount_paid += invoice.amount_total - invoice.amount_residual
                if (invoice.state == 'posted' and
                    invoice.move_type == 'in_refund' and
                    invoice.payment_state in ('in_payment', 'paid', 'partial', 'reversed')):
                    order.abk_amount_paid -= invoice.amount_total - invoice.amount_residual