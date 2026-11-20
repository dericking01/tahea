# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SCHEDULE_CHARGE_TYPES = [
    ('rent', 'Rent'),
    ('service_charge', 'Service Charge'),
    ('parking', 'Parking'),
    ('marketing_levy', 'Marketing Levy'),
    ('utility_fixed', 'Fixed Utility Charge'),
    ('other', 'Other Contractual Fee'),
    ('concession', 'Rent Concession'),
]
BILLABLE_LEASE_STATES = ('active', 'expiring', 'terminated', 'expired', 'renewed')


class ReBillingSchedule(models.Model):
    """One contractual billing obligation: (lease, obligation, period).

    The SQL unique constraint on (lease_id, obligation_key, period_start) plus the
    row lock taken when invoicing make the billing process idempotent: running it
    twice can never create two invoices for the same obligation and period."""
    _name = 're.billing.schedule'
    _description = 'Rental Billing Schedule'
    _order = 'invoice_date, lease_id, obligation_key'

    lease_id = fields.Many2one('re.lease', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='lease_id.currency_id', store=True)
    tenant_id = fields.Many2one(related='lease_id.tenant_id', store=True)
    property_id = fields.Many2one(related='lease_id.property_id', store=True, index=True)
    building_id = fields.Many2one(related='lease_id.building_id', store=True)
    manager_id = fields.Many2one(related='lease_id.manager_id', store=True)
    obligation_key = fields.Char(required=True, index=True)
    charge_type = fields.Selection(SCHEDULE_CHARGE_TYPES, required=True)
    charge_id = fields.Many2one('re.lease.charge', ondelete='set null')
    service_charge_budget_id = fields.Many2one('re.service.charge.budget', ondelete='set null')
    name = fields.Char('Description', required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    invoice_date = fields.Date('Scheduled Invoice Date', required=True, index=True)
    amount = fields.Monetary(required=True)
    explanation = fields.Text('Calculation', help='Audit trail of how the amount was computed.')
    invoice_id = fields.Many2one('account.move', copy=False, readonly=True, index=True)
    invoice_line_id = fields.Many2one('account.move.line', copy=False, readonly=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice Status')
    payment_state = fields.Selection(related='invoice_id.payment_state', string='Payment Status')
    state = fields.Selection([
        ('pending', 'To Invoice'),
        ('invoiced', 'Invoiced'),
        ('waived', 'Waived / Rent-free'),
    ], compute='_compute_state', store=True, index=True)
    is_late = fields.Boolean('Billing Overdue', compute='_compute_is_late', search='_search_is_late')

    _sql_constraints = [
        ('obligation_uniq', 'unique(lease_id, obligation_key, period_start)',
         'A billing obligation can only be scheduled once per lease and period.'),
    ]

    @api.depends('invoice_id', 'invoice_id.state', 'amount')
    def _compute_state(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state != 'cancel':
                rec.state = 'invoiced'
            elif rec.currency_id.is_zero(rec.amount):
                rec.state = 'waived'
            else:
                rec.state = 'pending'

    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for rec in self:
            grace = rec.company_id.re_billing_grace_days or 0
            rec.is_late = rec.state == 'pending' and rec.invoice_date < today - timedelta(days=grace)

    def _search_is_late(self, operator, value):
        today = fields.Date.context_today(self)
        grace = self.env.company.re_billing_grace_days or 0
        domain = [('state', '=', 'pending'), ('invoice_date', '<', today - timedelta(days=grace))]
        if (operator == '=' and value) or (operator == '!=' and not value):
            return domain
        return ['!', '&'] + domain

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.lease_id.name, rec.name)

    def unlink(self):
        if self.filtered(lambda s: s.state == 'invoiced'):
            raise UserError(_('Invoiced billing lines are part of the billing history and cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    def _re_lock(self):
        if self.ids:
            self.env.cr.execute('SELECT id FROM re_billing_schedule WHERE id IN %s FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset(['invoice_id', 'state'])

    def _re_create_invoices(self):
        """Create native customer invoices for pending schedule lines, grouped per
        lease and invoice date. Returns the created account.move records."""
        moves = self.env['account.move']
        lines = self.filtered(lambda s: s.state == 'pending')
        groups = defaultdict(lambda: self.browse())
        for line in lines:
            groups[(line.lease_id, line.invoice_date)] |= line
        for (lease, inv_date), group in groups.items():
            group._re_lock()
            group = group.filtered(lambda s: s.state == 'pending')
            if not group:
                continue
            total = sum(group.mapped('amount'))
            if lease.currency_id.compare_amounts(total, 0.0) < 0:
                self.env['re.exception']._re_raise(
                    'negative_billing', group[0], lease.company_id,
                    _('Billing for %(lease)s on %(date)s is negative (%(amount)s) because concessions exceed '
                      'charges. Review the concession and issue a credit note manually if appropriate.',
                      lease=lease.name, date=inv_date, amount=lease.currency_id.format(total)), lease=lease)
                continue
            move = self.env['account.move'].with_company(lease.company_id).create(
                lease._re_prepare_invoice_vals(inv_date, group))
            for sl in group:
                aml = move.invoice_line_ids.filtered(lambda l: l.re_schedule_line_id == sl)[:1]
                sl.write({'invoice_id': move.id, 'invoice_line_id': aml.id})
            if lease.company_id.re_auto_post_invoices:
                move.action_post()
            moves |= move
        return moves

    @api.model
    def _cron_generate_rental_invoices(self, date_to=None, lease_ids=None):
        """Scheduled billing run (idempotent). Each lease is processed in its own
        savepoint so one failure does not block the rest; failures are recorded as
        revenue-assurance exceptions."""
        date_to = date_to or fields.Date.context_today(self)
        domain = [('state', 'in', BILLABLE_LEASE_STATES)]
        if lease_ids:
            domain.append(('id', 'in', lease_ids))
        run = self.env['re.billing.run'].sudo().create({'date_to': date_to, 'user_id': self.env.uid})
        created = self.env['account.move']
        errors = []
        for lease in self.env['re.lease'].sudo().search(domain):
            try:
                with self.env.cr.savepoint():
                    lease = lease.with_company(lease.company_id)
                    lease._re_generate_schedule()
                    due = lease.schedule_ids.filtered(lambda s: s.state == 'pending' and s.invoice_date <= date_to)
                    created |= due._re_create_invoices()
            except Exception as e:  # noqa: BLE001 - logged and surfaced as an exception record
                _logger.exception('Rental billing failed for lease %s', lease.name)
                errors.append('%s: %s' % (lease.name, e))
                self.env['re.exception'].sudo()._re_raise(
                    'billing_failure', lease, lease.company_id,
                    _('Automatic billing failed for %(lease)s: %(err)s', lease=lease.name, err=e), lease=lease)
        run.write({'invoice_ids': [(6, 0, created.ids)], 'error_log': '\n'.join(errors), 'state': 'done'})
        return run


class ReBillingRun(models.Model):
    _name = 're.billing.run'
    _description = 'Rental Billing Run'
    _order = 'id desc'

    name = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code('re.billing.run') or '/')
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    date_to = fields.Date('Bill Up To', readonly=True)
    user_id = fields.Many2one('res.users', readonly=True)
    invoice_ids = fields.Many2many('account.move', string='Invoices Created', readonly=True)
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    error_log = fields.Text(readonly=True)
    state = fields.Selection([('running', 'Running'), ('done', 'Done')], default='running', readonly=True)

    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        return action


class ReLeaseInvoicing(models.Model):
    _inherit = 're.lease'

    def _re_prepare_invoice_vals(self, invoice_date, schedule_lines):
        self.ensure_one()
        company = self.company_id
        journal = company.re_rental_journal_id or self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('No sales journal configured for company %s.', company.name))
        line_vals = []
        for sl in schedule_lines:
            product = company._re_get_product(sl.charge_type)
            line_vals.append((0, 0, {
                'product_id': product.id,
                'name': '%s - %s' % (sl.name, ', '.join(self.unit_ids.mapped('name'))),
                'quantity': 1.0,
                'price_unit': sl.amount,
                'analytic_distribution': self.property_id._re_analytic_distribution(self.building_id),
                're_schedule_line_id': sl.id,
                're_charge_type': sl.charge_type,
                're_period_start': sl.period_start,
                're_period_end': sl.period_end,
                're_service_charge_budget_id': sl.service_charge_budget_id.id,
            }))
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.tenant_id.id,
            'invoice_date': invoice_date,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'ref': _('%(lease)s - %(period)s', lease=self.name,
                     period=min(schedule_lines.mapped('period_start'))),
            're_lease_id': self.id,
            'invoice_user_id': (self.user_id or self.env.user).id,
            'invoice_line_ids': line_vals,
        }
        if self.fiscal_position_id:
            vals['fiscal_position_id'] = self.fiscal_position_id.id
        if self.payment_term_id:
            vals['invoice_payment_term_id'] = self.payment_term_id.id
        else:
            vals['invoice_date_due'] = invoice_date + timedelta(days=self.payment_due_days or 0)
        return vals
