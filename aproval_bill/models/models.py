# -*- coding: utf-8 -*-
import re
from odoo import models, fields
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        readonly=True
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account'
    )

    # =====================================================
    # BILL PAYMENT STATUS (RELATED FROM VENDOR BILL)
    # =====================================================
    bill_payment_state = fields.Selection(
        related='bill_id.payment_state',
        string='Bill Payment Status',
        store=True,
        readonly=True
    )

    bill_payment_state_label = fields.Char(
        compute='_compute_bill_payment_state_label',
        string='Payment Status'
    )

    def _compute_bill_payment_state_label(self):
        for rec in self:
            mapping = {
                'not_paid': 'Not Paid',
                'partial': 'Partially Paid',
                'paid': 'Paid',
                'in_payment': 'In Payment',
                'reversed': 'Reversed',
            }
            rec.bill_payment_state_label = mapping.get(
                rec.bill_id.payment_state, ''
            )

    # =====================================================
    # CREATE VENDOR BILL
    # =====================================================
    def action_create_vendor_bill(self):
        self.ensure_one()

        if self.bill_id:
            raise UserError(
                f"A vendor bill has already been created for this approval request: {self.bill_id.name}. "
                "You cannot create another one."
            )

        vendor = self.partner_id
        if not vendor:
            raise UserError(
                "This approval request has no Contact (Vendor) assigned."
            )

        if not self.analytic_account_id:
            raise UserError(
                "Please select an Analytic Account before creating the Vendor Bill."
            )

        raw_description = self.reason or self.name
        line_description = re.sub(r'<[^>]+>', '', raw_description).strip()

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.today(),
            'name': '/',
            'ref': self.name,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'name': line_description,
                'quantity': 1,
                'price_unit': self.amount,
                'analytic_distribution': {
                    self.analytic_account_id.id: 100.0
                },
            })],
        })

        self.bill_id = bill.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
        }
