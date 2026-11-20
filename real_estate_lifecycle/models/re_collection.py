# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReCollectionCase(models.Model):
    """Structured arrears follow-up for a tenant. Balances always come from native
    receivables; disputed invoices are tracked separately from confirmed debt."""
    _name = 're.collection.case'
    _description = 'Collection Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    partner_id = fields.Many2one('res.partner', 'Tenant', required=True, index=True, tracking=True)
    lease_id = fields.Many2one('re.lease', domain="[('tenant_id', '=', partner_id)]")
    property_id = fields.Many2one('re.property', compute='_compute_property', store=True, readonly=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    user_id = fields.Many2one('res.users', 'Collector', default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([
        ('open', 'Open'), ('promise', 'Promise to Pay'), ('arrangement', 'Repayment Arrangement'),
        ('escalated', 'Escalated'), ('legal', 'Legal / Eviction Notice'), ('resolved', 'Resolved'),
        ('closed', 'Closed')], default='open', tracking=True)
    priority = fields.Selection([('0', 'Normal'), ('1', 'High'), ('2', 'Critical')], default='0')
    escalation_level = fields.Integer(default=0, tracking=True)
    overdue_amount = fields.Monetary('Confirmed Overdue', compute='_compute_balances')
    disputed_amount = fields.Monetary('Disputed', compute='_compute_balances')
    total_due = fields.Monetary('Total Receivable', compute='_compute_balances')
    oldest_days = fields.Integer('Oldest Overdue (days)', compute='_compute_balances')
    promise_ids = fields.One2many('re.collection.promise', 'case_id')
    next_action_date = fields.Date(tracking=True)
    review_required = fields.Boolean('Management Review Required', tracking=True)
    reviewed_by_id = fields.Many2one('res.users', readonly=True)
    reviewed_date = fields.Datetime(readonly=True)
    review_note = fields.Text()
    note = fields.Html()

    @api.depends('lease_id')
    def _compute_property(self):
        for rec in self:
            rec.property_id = rec.lease_id.property_id or rec.property_id

    def _receivable_lines(self):
        self.ensure_one()
        return self.env['account.move.line'].sudo().search([
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted'),
            ('reconciled', '=', False)])

    def _compute_balances(self):
        today = fields.Date.context_today(self)
        for rec in self:
            lines = rec._receivable_lines() if rec.partner_id else self.env['account.move.line']
            overdue = disputed = 0.0
            oldest = 0
            for line in lines:
                if line.amount_residual <= 0:
                    continue
                due = line.date_maturity or line.date
                if line.move_id.re_dispute_state == 'open':
                    disputed += line.amount_residual
                elif due < today:
                    overdue += line.amount_residual
                    oldest = max(oldest, (today - due).days)
            rec.overdue_amount = overdue
            rec.disputed_amount = disputed
            rec.total_due = sum(lines.mapped('amount_residual'))
            rec.oldest_days = oldest

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.collection.case') or '/'
        return super().create(vals_list)

    def action_send_reminder(self):
        template = self.env.ref('real_estate_lifecycle.mail_template_re_payment_reminder')
        for rec in self:
            rec.message_post_with_source(template, subtype_xmlid='mail.mt_comment')
            rec.next_action_date = fields.Date.context_today(self) + timedelta(days=7)

    def action_escalate(self):
        for rec in self:
            rec.escalation_level += 1
            rec.state = 'escalated'
            rec.review_required = True
            rec.priority = '2' if rec.escalation_level >= 2 else '1'
            manager = rec.property_id.manager_id or rec.lease_id.manager_id
            if manager:
                rec.activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                      summary=_('Escalated arrears: %s', rec.partner_id.name))

    def action_management_review(self):
        if not self.env.user.has_group('real_estate_lifecycle.group_re_finance_manager') and \
                not self.env.user.has_group('real_estate_lifecycle.group_re_portfolio_manager'):
            raise UserError(_('Only finance or portfolio managers can record a management review.'))
        self.write({'review_required': False, 'reviewed_by_id': self.env.uid,
                    'reviewed_date': fields.Datetime.now()})

    def action_legal(self):
        self.write({'state': 'legal'})

    def action_resolve(self):
        for rec in self:
            if rec.overdue_amount > 0 and not self.env.context.get('force'):
                raise UserError(_('Confirmed overdue balance remains (%s). Close as unresolved or collect first.',
                                  rec.currency_id.format(rec.overdue_amount)))
        self.write({'state': 'resolved'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_view_open_items(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Open Receivables'), 'res_model': 'account.move.line',
                'view_mode': 'list', 'domain': [('id', 'in', self._receivable_lines().ids)]}

    @api.model
    def _cron_collections(self):
        """Open a collection case for tenants with confirmed overdue balances older
        than the company threshold, and update promise statuses."""
        today = fields.Date.context_today(self)
        AML = self.env['account.move.line'].sudo()
        for company in self.env['res.company'].search([]):
            limit = today - timedelta(days=company.re_collection_case_days or 30)
            lines = AML.search([('company_id', '=', company.id), ('account_id.account_type', '=', 'asset_receivable'),
                                ('parent_state', '=', 'posted'), ('reconciled', '=', False),
                                ('amount_residual', '>', 0), ('date_maturity', '<', limit),
                                ('move_id.re_lease_id', '!=', False), ('move_id.re_dispute_state', '!=', 'open')])
            by_partner = {}
            for line in lines:
                p = line.partner_id.commercial_partner_id
                by_partner.setdefault(p, [0.0, line.move_id.re_lease_id])[0] += line.amount_residual
            for partner, (amount, lease) in by_partner.items():
                if amount < (company.re_collection_min_amount or 0.0):
                    continue
                if self.sudo().search_count([('partner_id', '=', partner.id), ('company_id', '=', company.id),
                                             ('state', 'not in', ('resolved', 'closed'))]):
                    continue
                self.sudo().create({'partner_id': partner.id, 'lease_id': lease.id, 'company_id': company.id,
                                    'user_id': (lease.manager_id or self.env.user).id,
                                    'next_action_date': today})
        self.env['re.collection.promise'].sudo().search([('state', '=', 'pending')])._update_status()


class ReCollectionPromise(models.Model):
    _name = 're.collection.promise'
    _description = 'Promise to Pay / Instalment'
    _order = 'date_promised'

    case_id = fields.Many2one('re.collection.case', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='case_id.currency_id')
    kind = fields.Selection([('promise', 'Promise to Pay'), ('instalment', 'Arrangement Instalment')],
                            default='promise', required=True)
    date_recorded = fields.Date(default=fields.Date.context_today, required=True)
    date_promised = fields.Date(required=True)
    amount = fields.Monetary(required=True)
    received_amount = fields.Monetary(readonly=True)
    state = fields.Selection([('pending', 'Pending'), ('kept', 'Kept'), ('broken', 'Broken')], default='pending')
    note = fields.Char()

    def _update_status(self):
        """A promise is kept when receipts from the tenant between the recording
        date and the promised date (+3 days grace) cover the promised amount."""
        AML = self.env['account.move.line'].sudo()
        today = fields.Date.context_today(self)
        for rec in self:
            case = rec.case_id
            receipts = AML.search([
                ('partner_id', 'child_of', case.partner_id.commercial_partner_id.id),
                ('company_id', '=', case.company_id.id),
                ('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted'),
                ('credit', '>', 0), ('move_id.move_type', 'in', ('entry',)),
                ('date', '>=', rec.date_recorded), ('date', '<=', rec.date_promised + timedelta(days=3))])
            received = sum(receipts.mapped('credit'))
            rec.received_amount = received
            if received >= rec.amount - 0.005:
                rec.state = 'kept'
            elif today > rec.date_promised + timedelta(days=3):
                rec.state = 'broken'
                case.message_post(body=_('Promise of %(amt)s due %(date)s was broken.',
                                         amt=case.currency_id.format(rec.amount), date=rec.date_promised))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.case_id.state in ('open', 'escalated'):
                rec.case_id.state = 'promise' if rec.kind == 'promise' else 'arrangement'
        return recs
