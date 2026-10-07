# -*- coding: utf-8 -*-
import re
from odoo import api, models, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, html2plaintext


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
        """Next number following the format of the most recent numbered bill of the journal,
        or the journal's starting format (e.g. BILL/2026/10/0001) when it has none yet."""
        self.ensure_one()
        last = self.search([
            ('journal_id', '=', self.journal_id.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('id', '!=', self.id),
            ('name', '!=', '/'),
            ('name', 'not ilike', 'new%'),
        ], order='date desc, id desc', limit=1)
        template = last.name or (self.date and self._get_starting_sequence())
        match = re.match(r'^(.*?)(\d+)$', template or '')
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

    # =====================================================
    # ACTION: LINK BILL (REPAIR BILL <-> APPROVAL RELATION)
    # =====================================================

    def _approval_references(self):
        """Approval names stored on the bill by action_create_vendor_bill (ref, origin, narration)."""
        self.ensure_one()
        refs = {self.ref, self.invoice_origin}
        narration = html2plaintext(self.narration or '')
        match = re.search(r'Vendor Bill created from Approval:\s*(.+?)\s*(?:\bVendor:|\n|$)', narration)
        if match:
            refs.add(match.group(1))
        return {r.strip() for r in refs if r and r.strip()}

    def _approval_amount_matches(self, approval):
        currency = approval.currency_id or approval.company_id.currency_id
        if currency != self.currency_id:
            return False
        return any(
            float_compare(amount, approval.amount, precision_rounding=currency.rounding) == 0
            for amount in (self.amount_untaxed, self.amount_total)
        )

    def _find_origin_approval(self):
        """Return (approval, error) for the approval this bill was generated from.

        Only returns an approval when the match is unambiguous; otherwise returns
        an empty recordset and the reason it could not be matched.
        """
        self.ensure_one()
        Approval = self.env['approval.request'].sudo()
        company_domain = [('company_id', 'in', (self.company_id.id, False))]

        approval = Approval.search([('bill_id', '=', self.id)])
        if len(approval) > 1:
            return Approval, "it is linked to several approvals (%s)" % ', '.join(approval.mapped('name'))
        if approval:
            # Already linked: the stored relation is authoritative, only the name may need fixing.
            return approval, None

        refs = self._approval_references()
        if refs:
            approval = Approval.search([('name', 'in', list(refs))] + company_domain)
            if not approval:
                return Approval, "no approval found with reference %s" % ', '.join(sorted(refs))
            if len(approval) > 1:
                return Approval, "reference %s matches several approvals (%s)" % (
                    ', '.join(sorted(refs)), ', '.join(approval.mapped('display_name')))
        elif not self.partner_id:
            return Approval, "it has neither an approval reference nor a vendor"
        else:
            # No stored reference: fall back to the full content of the bill, all criteria must match.
            descriptions = set(self.invoice_line_ids.mapped('name'))
            analytic_ids = {
                int(key) for line in self.invoice_line_ids
                for keys in (line.analytic_distribution or {})
                for key in keys.split(',')
            }
            approval = Approval.search([
                ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
                ('request_status', '=', 'approved'),
                ('bill_id', '=', False),
            ] + company_domain).filtered(lambda a: (
                self._approval_amount_matches(a)
                and a.analytic_account_id.id in analytic_ids
                and re.sub(r'<[^>]+>', '', a.reason or a.name or '').strip() in descriptions
            ))
            if not approval:
                return Approval, "it has no approval reference and no approval matches its partner, amount, analytic account and description"
            if len(approval) > 1:
                return Approval, "it has no approval reference and several approvals match its content (%s)" % ', '.join(approval.mapped('name'))

        # ---------------- CONSISTENCY CHECKS ----------------

        if approval.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            return Approval, "vendor %s differs from approval %s contact %s" % (
                self.partner_id.display_name, approval.name, approval.partner_id.display_name or '-')
        if not self._approval_amount_matches(approval):
            return Approval, "amount %s %s differs from approval %s amount %s %s" % (
                self.amount_untaxed, self.currency_id.name, approval.name, approval.amount,
                (approval.currency_id or approval.company_id.currency_id).name)
        if approval.bill_id and approval.bill_id.state != 'cancel':
            return Approval, "approval %s is already linked to bill %s" % (approval.name, approval.bill_id.name)
        others = self.sudo().search([
            ('id', '!=', self.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel'),
            ('company_id', '=', self.company_id.id),
            '|', ('invoice_origin', '=', approval.name), ('ref', '=', approval.name),
        ])
        if others:
            return Approval, "bills %s also reference approval %s" % (', '.join(others.mapped('name')), approval.name)
        return approval, None

    def action_link_approval_bill(self):
        """Relink selected vendor bills to their original approval and fix `New*` names."""
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError("Only accounting administrators can link bills to approvals.")

        skipped = []  # (bill label, reason)
        matches = {}  # bill -> approval
        for bill in self.sorted(lambda m: (m.date or fields.Date.today(), m.id)):
            if bill.move_type != 'in_invoice':
                skipped.append((bill.display_name, "it is not a vendor bill"))
            elif bill.state == 'cancel':
                skipped.append((bill.display_name, "it is cancelled"))
            else:
                approval, error = bill._find_origin_approval()
                if error:
                    skipped.append((bill.display_name, error))
                else:
                    matches[bill] = approval

        # The same approval claimed by several selected bills is ambiguous: skip all of them.
        by_approval = {}
        for bill, approval in matches.items():
            by_approval.setdefault(approval, []).append(bill)
        for approval, bills in by_approval.items():
            if len(bills) > 1:
                for bill in bills:
                    del matches[bill]
                    skipped.append((bill.display_name, "approval %s is claimed by several selected bills (%s)" % (
                        approval.name, ', '.join(b.display_name for b in bills))))

        linked, already_linked, renamed = [], [], []
        for bill, approval in matches.items():
            old_name = bill.display_name
            if approval.bill_id == bill:
                already_linked.append("%s → %s" % (old_name, approval.name))
            else:
                try:
                    with self.env.cr.savepoint():
                        approval.bill_id = bill
                        approval.message_post(body="Vendor bill %s relinked to this approval." % old_name)
                        bill.message_post(body="Bill relinked to approval %s." % approval.name)
                except (UserError, ValidationError) as e:
                    skipped.append((old_name, "linking failed: %s" % e))
                    continue
                linked.append("%s → %s" % (old_name, approval.name))

            # Draft bills are numbered on confirmation by _post now that they are linked.
            if bill.state != 'posted' or not bill._is_placeholder_name():
                continue
            try:
                with self.env.cr.savepoint():
                    new_name = bill._next_name_from_last_bill()
                    if not new_name:
                        raise UserError("no numbered bill in journal %s to follow" % bill.journal_id.name)
                    bill.name = new_name
                    bill.message_post(body="Bill renumbered from %s to %s." % (old_name, new_name))
            except (UserError, ValidationError) as e:
                skipped.append((old_name, "linked to %s but could not be renumbered: %s" % (approval.name, e)))
                continue
            renamed.append("%s → %s" % (old_name, new_name))

        parts = []
        if linked:
            parts.append("Linked %s bill(s): %s." % (len(linked), '; '.join(linked)))
        if already_linked:
            parts.append("Already linked: %s." % '; '.join(already_linked))
        if renamed:
            parts.append("Renumbered: %s." % '; '.join(renamed))
        if skipped:
            parts.append("Not linked (%s): %s." % (len(skipped), '; '.join(
                "%s: %s" % (name, reason) for name, reason in skipped)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Link Bill",
                'message': ' '.join(parts) or "Nothing to do.",
                'type': 'warning' if skipped else 'success',
                'sticky': bool(skipped),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
