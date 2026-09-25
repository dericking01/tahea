# -*- coding: utf-8 -*-
import re
from odoo import api, models, fields
from odoo.exceptions import UserError


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

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        domain=[('active', '=', True)],
        default=lambda self: self.env['res.currency'].search(
            [('active', '=', True)], limit=1),
    )

    bill_payment_state = fields.Selection(
        related='bill_id.payment_state',
        string='Bill Payment Status',
        store=True,
        readonly=True
    )

    # =====================================================
    # SUBMIT VALIDATION
    # =====================================================

    def action_confirm(self):
        for request in self:
            if request.has_amount != 'no' and request.amount < 1:
                raise UserError(
                    "The amount must be at least 1 before submitting the approval."
                )
        return super().action_confirm()

    # =====================================================
    # ACTION: CREATE VENDOR BILL (APPROVAL CONTACT AS VENDOR)
    # =====================================================

    def action_create_vendor_bill(self):
        self.ensure_one()

        # ---------------- VALIDATIONS ----------------

        if self.bill_id:
            raise UserError(
                f"A vendor bill already exists for this approval: {self.bill_id.name}"
            )

        if not self.partner_id:
            raise UserError(
                "Please select a Contact on the Approval Request before creating the Vendor Bill."
            )

        if not self.analytic_account_id:
            raise UserError(
                "Please select an Analytic Account before creating the Vendor Bill."
            )

        if not self.amount:
            raise UserError("Approval amount is missing.")

        # ---------------- APPROVAL CONTACT AS VENDOR ----------------

        vendor_partner = self.partner_id

        # ---------------- CLEAN DESCRIPTION ----------------

        raw_description = self.reason or self.name
        line_description = re.sub(r'<[^>]+>', '', raw_description).strip()

        # ---------------- BILL VALUES ----------------

        bill_vals = {
            'name': '/',
            'partner_id': vendor_partner.id,
            'currency_id': (self.currency_id or self.env.company.currency_id).id,
            'invoice_date': fields.Date.today(),
            'ref': self.name,
            'invoice_origin': self.name,
            'invoice_user_id': self.request_owner_id.id,
            'narration': (
                f"Vendor Bill created from Approval: {self.name}\n"
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


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # A draft bill whose name is a placeholder (e.g. "New") would be posted
        # with that literal name and collide on the unique (name, journal) index.
        for move in self:
            if move.state == 'draft' and move.name and move.name != '/' \
                    and move.name.strip().lower().startswith('new'):
                move.name = '/'
        return super()._post(soft=soft)
