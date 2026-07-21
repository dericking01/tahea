# -*- coding: utf-8 -*-
import re
from odoo import models, fields
from odoo.exceptions import UserError

BILL_NAME_RE = re.compile(r'^BILL/(\d{4})/(\d{2})/(\d+)$')


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    # =====================================================
    # FIELDS
    # =====================================================

    bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        readonly=True,
        copy=False
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True
    )

    bill_payment_state = fields.Selection(
        related='bill_id.payment_state',
        string='Bill Payment Status',
        store=True,
        readonly=True
    )

    # =====================================================
    # HELPER: NEXT VENDOR BILL SEQUENCE (BILL/YYYY/MM/NNNN)
    # =====================================================

    def _get_next_bill_name(self):
        today = fields.Date.today()
        prefix = f"BILL/{today.year:04d}/{today.month:02d}/"

        last_move = self.env['account.move'].search(
            [
                ('company_id', '=', self.env.company.id),
                ('name', '=like', f"{prefix}%"),
            ],
            order='name desc',
            limit=1,
        )

        next_number = 1
        if last_move:
            match = BILL_NAME_RE.match(last_move.name)
            if match:
                next_number = int(match.group(3)) + 1

        return f"{prefix}{next_number:04d}"

    # =====================================================
    # ACTION: CREATE VENDOR BILL (CONTACT AS VENDOR)
    # =====================================================

    def action_create_vendor_bill(self):
        self.ensure_one()

        # ---------------- VALIDATIONS ----------------

        if self.bill_id:
            raise UserError(
                f"A vendor bill already exists for this approval: {self.bill_id.name}"
            )

        if not self.request_owner_id:
            raise UserError("Approval Request has no Requestor.")

        if not self.partner_id:
            raise UserError(
                "Please set a Contact on the Approval Request before creating the Vendor Bill."
            )

        if not self.analytic_account_id:
            raise UserError(
                "Please select an Analytic Account before creating the Vendor Bill."
            )

        if not self.amount:
            raise UserError("Approval amount is missing.")

        # ---------------- CONTACT AS VENDOR ----------------

        vendor_partner = self.partner_id

        # ---------------- CLEAN DESCRIPTION ----------------

        raw_description = self.reason or self.name
        line_description = re.sub(r'<[^>]+>', '', raw_description).strip()

        # ---------------- BILL VALUES ----------------

        bill_vals = {
            'partner_id': vendor_partner.id,
            'name': self._get_next_bill_name(),
            'invoice_date': fields.Date.today(),
            'ref': self.name,
            'invoice_origin': self.name,
            'invoice_user_id': self.request_owner_id.id,
            'narration': (
                f"Reimbursement created from Approval: {self.name}\n"
                f"Requestor: {self.request_owner_id.name}\n"
                f"Vendor: {vendor_partner.name}"
            ),
            'invoice_line_ids': [(0, 0, {
                'name': line_description,
                'quantity': 1,
                'price_unit': self.amount,
                'analytic_distribution': {
                    self.analytic_account_id.id: 100.0
                },
            })],
        }

        # ---------------- CREATE BILL THE ODOO WAY ----------------
        # This context is what fixes NEW / NEW1 and applies correct journal & sequence
        Move = self.env['account.move'].with_context(default_move_type='in_invoice')
        bill = Move.create(bill_vals)

        # ---------------- LINK BILL ----------------

        self.bill_id = bill.id

        # ---------------- OPEN BILL ----------------

        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bill',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
        }
