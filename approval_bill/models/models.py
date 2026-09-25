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

    def _is_placeholder_name(self):
        self.ensure_one()
        return not self.name or self.name == '/' or self.name.strip().lower().startswith('new')

    def _next_name_from_last_bill(self):
        """Next number following the format of the most recent numbered bill of the journal."""
        self.ensure_one()
        last = self.search([
            ('journal_id', '=', self.journal_id.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('id', '!=', self.id),
            ('name', '!=', '/'),
            ('name', 'not ilike', 'new%'),
        ], order='date desc, id desc', limit=1)
        match = re.match(r'^(.*?)(\d+)$', last.name or '')
        if not match:
            return False
        prefix, digits = match.groups()
        date = self.date or fields.Date.context_today(self)
        if last.date:
            prefix = prefix.replace('/%d/' % last.date.year, '/%d/' % date.year)
            prefix = prefix.replace('/%02d/' % last.date.month, '/%02d/' % date.month)
        used = self.search([
            ('journal_id', '=', self.journal_id.id),
            ('name', '=like', prefix.replace('_', r'\_').replace('%', r'\%') + '%'),
        ]).mapped('name')
        numbers = [int(n.group(1)) for n in (re.match(r'^%s(\d+)$' % re.escape(prefix), u) for u in used) if n]
        number = max(numbers, default=int(digits) if prefix == match.group(1) else 0) + 1
        return '%s%s' % (prefix, str(number).zfill(len(digits)))

    def _post(self, soft=True):
        approval_bills = self.env['approval.request'].search([('bill_id', 'in', self.ids)]).bill_id
        for move in self:
            if move.state != 'draft' or not move._is_placeholder_name():
                continue
            name = move in approval_bills and move._next_name_from_last_bill()
            move.name = name or '/'
        return super()._post(soft=soft)
