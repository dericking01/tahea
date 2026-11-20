# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ReSecurityDeposit(models.Model):
    """Refundable tenant deposit.

    Accounting treatment (native Odoo documents only):
    * Demand: customer invoice whose line is posted to the company's configured
      *Tenant Deposit Liability* account -> Dr Receivable / Cr Deposit Liability.
      No income is recognised when the money is received.
    * Receipt: native customer payment reconciled with that invoice.
    * Refund (after approval): customer credit note with
        Dr Deposit Liability (full deposit held)
        Cr Deduction Income (each approved deduction)
        Cr Receivable (net refundable)
      followed by a native outbound payment to the tenant (or reconciliation of the
      credit note against outstanding rent)."""
    _name = 're.security.deposit'
    _description = 'Tenant Security Deposit'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin']
    _order = 'id desc'
    _re_approval_document_type = 'deposit_refund'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    lease_id = fields.Many2one('re.lease', required=True, index=True, ondelete='restrict')
    tenant_id = fields.Many2one(related='lease_id.tenant_id', store=True)
    property_id = fields.Many2one(related='lease_id.property_id', store=True, index=True)
    building_id = fields.Many2one(related='lease_id.building_id', store=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True, index=True)
    manager_id = fields.Many2one(related='lease_id.manager_id', store=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    purpose = fields.Selection([
        ('security', 'Security / Damage Deposit'), ('utility', 'Utility Deposit'),
        ('key', 'Key / Access Card Deposit'), ('fitout', 'Fit-out Deposit'), ('other', 'Other')],
        default='security', required=True)
    amount = fields.Monetary(required=True, tracking=True)
    refund_conditions = fields.Text(default=lambda self: _(
        'Refundable at the end of the lease after inspection, less unpaid amounts and the cost of '
        'repairing damage beyond fair wear and tear.'))
    state = fields.Selection([
        ('draft', 'To Invoice'),
        ('invoiced', 'Awaiting Receipt'),
        ('held', 'Held'),
        ('refund_requested', 'Refund Requested'),
        ('refund_approved', 'Refund Approved'),
        ('refunded', 'Refund Issued'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, compute='_compute_state', store=True, readonly=False)
    invoice_id = fields.Many2one('account.move', 'Deposit Invoice', readonly=True, copy=False)
    received_amount = fields.Monetary(compute='_compute_amounts', store=True)
    receipt_date = fields.Date(compute='_compute_amounts', store=True)
    held_amount = fields.Monetary('Liability Held', compute='_compute_amounts', store=True)
    deduction_ids = fields.One2many('re.deposit.deduction', 'deposit_id')
    deduction_total = fields.Monetary(compute='_compute_refund', store=True)
    refund_amount = fields.Monetary('Net Refund', compute='_compute_refund', store=True)
    refund_move_id = fields.Many2one('account.move', 'Refund Credit Note', readonly=True, copy=False)
    refund_payment_state = fields.Selection(related='refund_move_id.payment_state', string='Refund Payment')
    note = fields.Text()

    @api.depends('invoice_id.payment_state', 'invoice_id.state', 'invoice_id.amount_residual', 'refund_move_id.state')
    def _compute_amounts(self):
        for rec in self:
            inv = rec.invoice_id
            if inv and inv.state == 'posted':
                rec.received_amount = inv.amount_total - inv.amount_residual
                pay_dates = inv.line_ids.matched_credit_ids.mapped('max_date')
                rec.receipt_date = max(pay_dates) if pay_dates and rec.received_amount else False
            else:
                rec.received_amount = 0.0
                rec.receipt_date = False
            released = rec.refund_move_id and rec.refund_move_id.state == 'posted'
            rec.held_amount = 0.0 if released else rec.received_amount

    @api.depends('invoice_id.state', 'invoice_id.payment_state', 'refund_move_id.state')
    def _compute_state(self):
        for rec in self:
            if rec.state in ('cancelled', 'refund_requested', 'refund_approved') and not (
                    rec.refund_move_id and rec.refund_move_id.state == 'posted'):
                rec.state = rec.state
                continue
            if rec.refund_move_id and rec.refund_move_id.state == 'posted':
                rec.state = 'refunded'
            elif rec.invoice_id and rec.invoice_id.state == 'posted' and rec.invoice_id.payment_state in (
                    'paid', 'in_payment', 'partial'):
                rec.state = 'held'
            elif rec.invoice_id and rec.invoice_id.state != 'cancel':
                rec.state = 'invoiced'
            else:
                rec.state = rec.state if rec.state == 'cancelled' else 'draft'

    @api.depends('deduction_ids.amount', 'held_amount', 'amount')
    def _compute_refund(self):
        for rec in self:
            rec.deduction_total = sum(rec.deduction_ids.mapped('amount'))
            base = rec.held_amount if rec.state not in ('refunded',) else rec.received_amount
            rec.refund_amount = max(0.0, (base or rec.received_amount) - rec.deduction_total)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.security.deposit') or '/'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Deposit amount must be positive.'))

    def _re_approval_amount(self):
        return self.refund_amount

    def _deposit_account(self):
        account = self.company_id.re_deposit_account_id
        if not account:
            raise UserError(_('Configure the "Tenant Deposit Liability Account" in Real Estate settings for %s. '
                              'Refundable deposits must never be posted to income.', self.company_id.name))
        if account.internal_group != 'liability':
            raise UserError(_('The deposit account %s must be a liability account.', account.display_name))
        return account

    def _journal(self):
        company = self.company_id
        return company.re_rental_journal_id or self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)

    def action_create_invoice(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state != 'cancel':
                raise UserError(_('Deposit %s is already invoiced.', rec.name))
            account = rec._deposit_account()
            move = self.env['account.move'].with_company(rec.company_id).create({
                'move_type': 'out_invoice',
                'partner_id': rec.tenant_id.id,
                'invoice_date': fields.Date.context_today(self),
                'journal_id': rec._journal().id,
                'currency_id': rec.currency_id.id,
                'invoice_origin': rec.lease_id.name,
                'ref': _('Security deposit %s', rec.name),
                're_lease_id': rec.lease_id.id,
                're_deposit_id': rec.id,
                'invoice_line_ids': [(0, 0, {
                    'name': _('%(purpose)s - %(lease)s (refundable, held as liability)',
                              purpose=dict(self._fields['purpose'].selection)[rec.purpose], lease=rec.lease_id.name),
                    'account_id': account.id,
                    'quantity': 1,
                    'price_unit': rec.amount,
                    'tax_ids': [(6, 0, [])],
                    'analytic_distribution': rec.property_id._re_analytic_distribution(rec.building_id),
                    're_charge_type': 'deposit',
                })],
            })
            rec.invoice_id = move
            if rec.company_id.re_auto_post_invoices:
                move.action_post()
        return self._open_move(self.invoice_id)

    def action_request_refund(self):
        for rec in self:
            if rec.state != 'held':
                raise UserError(_('Only deposits that are held can be refunded.'))
            if rec.lease_id.state in ('active', 'expiring', 'approved'):
                raise UserError(_('Lease %s is still running. Terminate or let it expire before refunding '
                                  'the deposit.', rec.lease_id.name))
            if rec.currency_id.compare_amounts(rec.deduction_total, rec.held_amount) > 0:
                raise UserError(_('Deductions exceed the deposit held.'))
            rec.state = 'refund_requested'
            if rec._re_request_approval():
                rec.state = 'refund_approved'

    def action_approve_refund(self):
        self._re_approve()
        self.write({'state': 'refund_approved'})

    def _re_after_reject(self):
        self.write({'state': 'held'})

    def action_create_refund(self):
        for rec in self:
            if rec.state != 'refund_approved' or not rec._re_is_approved():
                raise UserError(_('The refund of %s must be approved first.', rec.name))
            account = rec._deposit_account()
            lines = [(0, 0, {
                'name': _('Release of deposit %s', rec.name),
                'account_id': account.id, 'quantity': 1, 'price_unit': rec.held_amount,
                'tax_ids': [(6, 0, [])], 're_charge_type': 'deposit',
                'analytic_distribution': rec.property_id._re_analytic_distribution(rec.building_id),
            })]
            for ded in rec.deduction_ids:
                ded_account = ded.account_id or rec.company_id.re_deposit_deduction_account_id
                if not ded_account:
                    raise UserError(_('Configure a deduction income account (settings) or set one on deduction "%s".',
                                      ded.name))
                lines.append((0, 0, {
                    'name': _('Deduction: %s', ded.name), 'account_id': ded_account.id, 'quantity': 1,
                    'price_unit': -ded.amount, 'tax_ids': [(6, 0, [])], 're_charge_type': 'deposit_deduction',
                    'analytic_distribution': rec.property_id._re_analytic_distribution(rec.building_id),
                }))
            move = self.env['account.move'].with_company(rec.company_id).create({
                'move_type': 'out_refund',
                'partner_id': rec.tenant_id.id,
                'invoice_date': fields.Date.context_today(self),
                'journal_id': rec._journal().id,
                'currency_id': rec.currency_id.id,
                'invoice_origin': rec.name,
                'ref': _('Deposit refund %s', rec.name),
                're_lease_id': rec.lease_id.id,
                're_deposit_id': rec.id,
                're_approval_state': 'approved',
                're_approved_by_id': rec.re_approved_by_id.id,
                're_approved_date': rec.re_approved_date,
                'invoice_line_ids': lines,
            })
            move.action_post()
            rec.refund_move_id = move
            rec.message_post(body=_('Refund credit note %s posted. Register the outbound payment to the tenant '
                                    'from the credit note.', move.name))
        return self._open_move(self.refund_move_id)

    def action_cancel(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == 'posted':
                raise UserError(_('Reverse the posted deposit invoice through a credit note before cancelling.'))
            if rec.invoice_id and rec.invoice_id.state == 'draft':
                rec.invoice_id.button_cancel()
        self.write({'state': 'cancelled'})

    def _open_move(self, moves):
        if len(moves) == 1:
            return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': moves.id,
                    'view_mode': 'form'}
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('id', 'in', moves.ids)]}


class ReDepositDeduction(models.Model):
    _name = 're.deposit.deduction'
    _description = 'Deposit Deduction'

    deposit_id = fields.Many2one('re.security.deposit', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='deposit_id.currency_id')
    name = fields.Char('Reason', required=True)
    amount = fields.Monetary(required=True)
    account_id = fields.Many2one('account.account', 'Income / Recovery Account')
    work_order_id = fields.Many2one('re.work.order', 'Related Work Order')
    attachment_ids = fields.Many2many('ir.attachment', string='Evidence')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Deductions must be positive.'))

    def _check_editable(self):
        if self.mapped('deposit_id').filtered(lambda d: d.state in ('refund_requested', 'refund_approved', 'refunded')):
            raise UserError(_('Deductions cannot be changed once a refund has been requested.'))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._check_editable()
        return recs

    def write(self, vals):
        self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
