# -*- coding: utf-8 -*-
"""Revenue assurance & financial control engine.

Each *scan* check is a method ``_check_<code>(control)`` returning a list of
findings. Findings are upserted into ``re.exception`` by a deterministic key.
When a later scan no longer detects an open finding, it is automatically marked
resolved (with an audit message), so the dashboard always reflects reality.

The engine NEVER modifies accounting entries: it only recommends investigation.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CHECK_CODES = [
    # Revenue leakage
    ('unit_occupied_no_lease', 'Occupied unit without an active lease'),
    ('lease_missing_invoice', 'Active lease with billing due but not invoiced'),
    ('escalation_not_applied', 'Rent escalation date passed without approval'),
    ('duplicate_rent_invoice', 'Duplicate rent invoice for the same period'),
    ('expired_lease_occupied', 'Expired / terminated lease with ongoing occupancy'),
    ('utility_unbilled', 'Recharged utility consumption not billed'),
    ('service_charge_missing', 'Service charge missing from lease billing'),
    ('payment_unallocated', 'Tenant payment received but not allocated'),
    ('unusual_adjustment', 'Unapproved tenant credit note / receivable adjustment'),
    ('refund_unapproved', 'Refund paid to tenant without approval'),
    ('deposit_outstanding', 'Security deposit not received'),
    ('lease_unsigned', 'Active lease without signed agreement'),
    # Financial controls
    ('vendor_bill_over_approved', 'Vendor bills above approved work-order budget / quotation'),
    ('unapproved_spend', 'Maintenance expenditure without approval'),
    ('bill_without_po', 'Contractor bill without purchase order'),
    ('duplicate_vendor_bill', 'Possible duplicate vendor bill'),
    ('missing_analytic', 'Property expenditure without property analytic allocation'),
    ('wrong_property_allocation', 'Expenditure allocated to a different property'),
    ('service_charge_overrun', 'Service-charge budget overrun'),
    ('service_charge_unreconciled', 'Service-charge period ended but not reconciled'),
    ('emergency_not_reviewed', 'Emergency work not reviewed'),
    ('contractor_non_compliant', 'Contractor with expired licence / insurance on open work'),
    ('insurance_expiry', 'Property insurance expired or expiring'),
    # Event based (raised by processes, resolved manually)
    ('billing_failure', 'Automatic billing failure'),
    ('termination_overbilled', 'Invoice covers period after lease termination'),
    ('negative_billing', 'Negative billing (concession exceeds charges)'),
    ('control_override', 'Financial control overridden'),
]
EVENT_CODES = {'billing_failure', 'termination_overbilled', 'negative_billing', 'control_override'}
LIVE = ('active', 'expiring')


class ReControlCheck(models.Model):
    _name = 're.control.check'
    _description = 'Revenue Assurance / Financial Control'
    _order = 'category, sequence, id'

    code = fields.Selection(CHECK_CODES, required=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([('revenue', 'Revenue Assurance'), ('financial', 'Financial Control'),
                                 ('operational', 'Operational')], required=True, default='revenue')
    active = fields.Boolean(default=True)
    severity = fields.Selection([('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                                default='medium', required=True)
    threshold_days = fields.Integer('Grace / Threshold (days)', default=0)
    threshold_amount = fields.Float('Threshold Amount', default=0.0)
    threshold_pct = fields.Float('Threshold (%)', default=0.0)
    responsible_user_id = fields.Many2one('res.users', 'Default Responsible',
                                          help='If empty, the property manager is responsible.')
    description = fields.Text(translate=True)
    recommendation = fields.Text(translate=True)
    last_run = fields.Datetime(readonly=True)
    open_count = fields.Integer(compute='_compute_open_count')

    _sql_constraints = [('code_uniq', 'unique(code)', 'One control per check code.')]

    def _compute_open_count(self):
        data = self.env['re.exception']._read_group([('state', 'in', ('new', 'investigating'))], ['check_code'],
                                                    ['__count'])
        counts = {code: count for code, count in data}
        for rec in self:
            rec.open_count = counts.get(rec.code, 0)

    def action_run(self):
        self.env['re.exception'].run_checks(self.mapped('code'))
        return True


class ReException(models.Model):
    _name = 're.exception'
    _description = 'Revenue Assurance / Control Exception'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state_sequence, severity_sequence desc, detected_date desc, id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    check_code = fields.Selection(CHECK_CODES, required=True, index=True, readonly=True)
    category = fields.Selection([('revenue', 'Revenue Assurance'), ('financial', 'Financial Control'),
                                 ('operational', 'Operational')], readonly=True)
    severity = fields.Selection([('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                                default='medium', tracking=True)
    severity_sequence = fields.Integer(compute='_compute_sequences', store=True)
    state_sequence = fields.Integer(compute='_compute_sequences', store=True)
    key = fields.Char(required=True, index=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    property_id = fields.Many2one('re.property', index=True, readonly=True)
    building_id = fields.Many2one('re.building', readonly=True)
    unit_id = fields.Many2one('re.unit', readonly=True)
    lease_id = fields.Many2one('re.lease', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    reference = fields.Char('Source Document', readonly=True)
    amount = fields.Monetary(readonly=True)
    description = fields.Text(readonly=True)
    recommendation = fields.Text(readonly=True)
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True)
    state = fields.Selection([
        ('new', 'New'), ('investigating', 'Investigating'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')],
        default='new', tracking=True, index=True)
    detected_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_seen = fields.Datetime(readonly=True)
    resolved_date = fields.Datetime(readonly=True)
    resolved_by_id = fields.Many2one('res.users', readonly=True)
    auto_resolved = fields.Boolean(readonly=True)
    reopen_count = fields.Integer(readonly=True)
    resolution_note = fields.Text(tracking=True)
    age_days = fields.Integer(compute='_compute_age')

    _sql_constraints = [('key_uniq', 'unique(key)', 'Exception key must be unique.')]

    @api.depends('severity', 'state')
    def _compute_sequences(self):
        sev = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        st = {'new': 1, 'investigating': 2, 'resolved': 3, 'dismissed': 4}
        for rec in self:
            rec.severity_sequence = sev.get(rec.severity, 0)
            rec.state_sequence = st.get(rec.state, 9)

    def _compute_age(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.age_days = (now - rec.detected_date).days if rec.detected_date else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.exception') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def action_investigate(self):
        self.write({'state': 'investigating', 'user_id': self.user_id.id or self.env.uid})

    def action_resolve(self):
        for rec in self:
            if not rec.resolution_note:
                raise UserError(_('Enter a resolution note explaining the corrective action for %s.', rec.name))
        self.write({'state': 'resolved', 'resolved_date': fields.Datetime.now(), 'resolved_by_id': self.env.uid})

    def action_dismiss(self):
        for rec in self:
            if not rec.resolution_note:
                raise UserError(_('Explain why %s is not an issue before dismissing it.', rec.name))
        self.write({'state': 'dismissed', 'resolved_date': fields.Datetime.now(), 'resolved_by_id': self.env.uid})

    def action_reopen(self):
        self.write({'state': 'new', 'resolved_date': False, 'resolved_by_id': False, 'auto_resolved': False})

    def action_open_source(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_('No source document.'))
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form'}

    # ------------------------------------------------------------------
    @api.model
    def _finding(self, key, record, **kw):
        kw.update({'key': key, 'record': record})
        return kw

    @api.model
    def _re_raise(self, code, record, company, description, lease=None, prop=None, amount=0.0, key_suffix=''):
        """Create (or refresh) an event-based exception."""
        control = self.env['re.control.check'].sudo().search([('code', '=', code)], limit=1)
        key = '%s:%s:%s%s' % (code, record._name, record.id, key_suffix)
        existing = self.sudo().search([('key', '=', key)], limit=1)
        prop = prop or (lease and lease.property_id) or self.env['re.property']
        vals = {
            'check_code': code, 'category': control.category or 'revenue', 'severity': control.severity or 'high',
            'company_id': company.id, 'property_id': prop.id, 'lease_id': lease.id if lease else False,
            'partner_id': lease.tenant_id.id if lease else False, 'res_model': record._name, 'res_id': record.id,
            'reference': record.display_name, 'description': description, 'amount': amount,
            'recommendation': control.recommendation, 'last_seen': fields.Datetime.now(),
            'user_id': (control.responsible_user_id or prop.manager_id).id or False,
        }
        if existing:
            if existing.state in ('resolved', 'dismissed'):
                vals.update(state='new', reopen_count=existing.reopen_count + 1)
            existing.write(vals)
            return existing
        vals['key'] = key
        return self.sudo().create(vals)

    @api.model
    def run_checks(self, codes=None):
        controls = self.env['re.control.check'].sudo().search([])
        if codes:
            controls = controls.filtered(lambda c: c.code in codes)
        now = fields.Datetime.now()
        summary = {}
        for control in controls:
            if control.code in EVENT_CODES:
                continue
            method = getattr(self.sudo(), '_check_%s' % control.code, None)
            if not method:
                continue
            try:
                with self.env.cr.savepoint():
                    findings = method(control)
                    self._upsert(control, findings, now)
                    control.last_run = now
                    summary[control.code] = len(findings)
            except Exception:  # noqa: BLE001 - one broken check must not stop the others
                _logger.exception('Control check %s failed', control.code)
        return summary

    def _upsert(self, control, findings, now):
        Exc = self.sudo()
        seen = set()
        for f in findings:
            record = f['record']
            key = '%s:%s' % (control.code, f['key'])
            seen.add(key)
            prop = f.get('property') or self.env['re.property']
            company = f.get('company') or prop.company_id or self.env.company
            vals = {
                'description': f.get('description'),
                'amount': f.get('amount', 0.0),
                'last_seen': now,
                'severity': f.get('severity') or control.severity,
            }
            existing = Exc.search([('key', '=', key)], limit=1)
            if existing:
                if existing.state == 'resolved':
                    vals.update(state='new', reopen_count=existing.reopen_count + 1, auto_resolved=False,
                                resolved_date=False)
                    existing.message_post(body=_('Condition detected again - reopened.'))
                if existing.state != 'dismissed':
                    existing.write(vals)
                continue
            lease = f.get('lease') or self.env['re.lease']
            vals.update({
                'key': key, 'check_code': control.code, 'category': control.category,
                'company_id': company.id, 'property_id': prop.id,
                'building_id': (f.get('building') or lease.building_id).id or False,
                'unit_id': f.get('unit') and f['unit'].id or False,
                'lease_id': lease.id or False,
                'partner_id': (f.get('partner') or lease.tenant_id).id or False,
                'res_model': record._name, 'res_id': record.id, 'reference': record.display_name,
                'recommendation': control.recommendation,
                'user_id': (control.responsible_user_id or prop.manager_id).id or False,
            })
            exc = Exc.create(vals)
            if exc.user_id:
                exc.activity_schedule('mail.mail_activity_data_todo', user_id=exc.user_id.id,
                                      summary=_('Investigate: %s', control.name))
        stale = Exc.search([('check_code', '=', control.code), ('state', 'in', ('new', 'investigating')),
                            ('key', 'not in', list(seen) or [''])])
        for exc in stale:
            exc.write({'state': 'resolved', 'auto_resolved': True, 'resolved_date': now,
                       'resolution_note': (exc.resolution_note or '') + _('\nCondition no longer detected on %s.', now)})
            exc.activity_ids.action_feedback(feedback=_('Auto-resolved: condition no longer detected.'))

    @api.model
    def _cron_run_checks(self):
        self.run_checks()

    # ------------------------------------------------------------------
    # Check implementations
    # ------------------------------------------------------------------
    def _today(self):
        return fields.Date.context_today(self)

    def _check_unit_occupied_no_lease(self, control):
        res = []
        units = self.env['re.unit'].search([('occupancy_status', '=', 'occupied'), ('is_lettable', '=', True)])
        for unit in units.filtered(lambda u: u.rental_status != 'let'):
            res.append(self._finding('unit:%s' % unit.id, unit, property=unit.property_id, building=unit.building_id,
                                     unit=unit, amount=unit.market_rent, description=_(
                                         'Unit %(unit)s is marked occupied but has no active lease, so no rent is being '
                                         'billed (expected monthly rent %(rent)s).', unit=unit.display_name,
                                         rent=unit.currency_id.format(unit.market_rent))))
        return res

    def _check_lease_missing_invoice(self, control):
        res = []
        today = self._today()
        Schedule = self.env['re.billing.schedule']
        leases = self.env['re.lease'].search([('state', 'in', LIVE + ('terminated', 'expired', 'renewed'))])
        for lease in leases:
            grace = control.threshold_days or lease.company_id.re_billing_grace_days or 0
            late = Schedule.search([('lease_id', '=', lease.id), ('state', '=', 'pending'),
                                    ('invoice_date', '<', today - timedelta(days=grace))])
            missing_schedule = lease.state in LIVE and not lease.schedule_ids
            if late or missing_schedule:
                res.append(self._finding('lease:%s' % lease.id, lease, property=lease.property_id, lease=lease,
                                         amount=sum(late.mapped('amount')), description=_(
                                             '%(count)s billing obligation(s) totalling %(amt)s for lease %(lease)s were '
                                             'due for invoicing but no invoice exists.%(nosched)s', count=len(late),
                                             amt=lease.currency_id.format(sum(late.mapped('amount'))), lease=lease.name,
                                             nosched=_(' The lease has no billing schedule.') if missing_schedule else '')))
        return res

    def _check_escalation_not_applied(self, control):
        res = []
        escs = self.env['re.lease.escalation'].search([
            ('state', 'in', ('draft', 'to_approve')), ('effective_date', '<=', self._today()),
            ('lease_id.state', 'in', LIVE)])
        for esc in escs:
            res.append(self._finding('esc:%s' % esc.id, esc, property=esc.lease_id.property_id, lease=esc.lease_id,
                                     amount=(esc.rent_after - esc.rent_before), description=_(
                                         'Escalation effective %(date)s on %(lease)s is still "%(state)s"; invoices are '
                                         'being raised at the old rent.', date=esc.effective_date, lease=esc.lease_id.name,
                                         state=dict(esc._fields['state'].selection)[esc.state])))
        return res

    def _check_duplicate_rent_invoice(self, control):
        self.env['account.move.line'].flush_model()
        self.env['account.move'].flush_model()
        self.env.cr.execute("""
            SELECT m.re_lease_id, l.re_period_start, array_agg(DISTINCT m.id)
              FROM account_move_line l
              JOIN account_move m ON m.id = l.move_id
             WHERE l.re_charge_type = 'rent' AND m.move_type = 'out_invoice'
               AND m.state != 'cancel' AND COALESCE(m.payment_state, '') != 'reversed'
               AND m.re_lease_id IS NOT NULL AND l.re_period_start IS NOT NULL
          GROUP BY m.re_lease_id, l.re_period_start
            HAVING COUNT(DISTINCT m.id) > 1
        """)
        res = []
        for lease_id, period, move_ids in self.env.cr.fetchall():
            lease = self.env['re.lease'].browse(lease_id)
            moves = self.env['account.move'].browse(move_ids)
            res.append(self._finding('lease:%s:%s' % (lease_id, period), moves[0], property=lease.property_id,
                                     lease=lease, amount=sum(moves.mapped('amount_total')), description=_(
                                         'Rent for %(lease)s period starting %(p)s appears on %(n)s invoices: %(names)s.',
                                         lease=lease.name, p=period, n=len(moves),
                                         names=', '.join(m.name or m.display_name for m in moves))))
        return res

    def _check_expired_lease_occupied(self, control):
        res = []
        today = self._today()
        leases = self.env['re.lease'].search([('state', 'in', ('expired', 'terminated')), ('move_out_date', '=', False),
                                              ('effective_end_date', '<', today - timedelta(days=control.threshold_days))])
        for lease in leases:
            occupied = lease.unit_ids.filtered(lambda u: u.occupancy_status == 'occupied' and u.rental_status != 'let')
            if occupied:
                res.append(self._finding('lease:%s' % lease.id, lease, property=lease.property_id, lease=lease,
                                         amount=lease.current_rent, description=_(
                                             'Lease %(lease)s ended on %(date)s but %(units)s is still occupied without a '
                                             'renewal (holding over unbilled).', lease=lease.name,
                                             date=lease.effective_end_date,
                                             units=', '.join(occupied.mapped('display_name')))))
        return res

    def _check_utility_unbilled(self, control):
        res = []
        limit = self._today() - timedelta(days=control.threshold_days or 7)
        readings = self.env['re.meter.reading'].search([('billable', '=', True), ('state', 'in', ('draft', 'confirmed')),
                                                        ('date', '<', limit), ('cost', '>', 0)])
        for r in readings:
            res.append(self._finding('reading:%s' % r.id, r, property=r.property_id, lease=r.lease_id, amount=r.cost,
                                     description=_('Meter %(m)s reading of %(d)s (%(c)s) is recharged under %(lease)s '
                                                   'but has not been billed.', m=r.meter_id.name, d=r.date,
                                                   c=r.currency_id.format(r.cost) if r.currency_id else r.cost,
                                                   lease=r.lease_id.name)))
        return res

    def _check_service_charge_missing(self, control):
        res = []
        today = self._today()
        budgets = self.env['re.service.charge.budget'].search([('state', '=', 'applied'), ('date_from', '<=', today),
                                                               ('date_to', '>=', today)])
        for budget in budgets:
            domain = [('property_id', '=', budget.property_id.id), ('state', 'in', LIVE),
                      ('service_charge_applicable', '=', True)]
            if budget.building_id:
                domain.append(('building_id', '=', budget.building_id.id))
            for lease in self.env['re.lease'].search(domain):
                has = lease.charge_ids.filtered(lambda c: c.charge_type == 'service_charge' and c.active and (
                    not c.date_from or c.date_from <= today) and (not c.date_to or c.date_to >= today))
                if not has:
                    res.append(self._finding('lease:%s:%s' % (lease.id, budget.id), lease, property=lease.property_id,
                                             lease=lease, description=_(
                                                 'Lease %(lease)s has a service-charge obligation but no service charge '
                                                 'from budget %(b)s is being billed.', lease=lease.name, b=budget.name)))
        return res

    def _check_payment_unallocated(self, control):
        res = []
        limit = self._today() - timedelta(days=control.threshold_days)
        lines = self.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted'),
            ('reconciled', '=', False), ('amount_residual', '<', 0), ('partner_id.re_is_tenant', '=', True),
            ('move_id.move_type', '=', 'entry'), ('date', '<=', limit)])
        for line in lines:
            lease = self.env['re.lease'].search([('tenant_id', '=', line.partner_id.commercial_partner_id.id)],
                                                order='date_start desc', limit=1)
            res.append(self._finding('aml:%s' % line.id, line.move_id, property=lease.property_id,
                                     company=line.company_id, lease=lease, partner=line.partner_id,
                                     amount=-line.amount_residual, description=_(
                                         'Receipt %(ref)s of %(amt)s from %(p)s dated %(d)s is not allocated to any '
                                         'invoice (advance payment, overpayment or misallocation).',
                                         ref=line.move_id.name, amt=line.company_currency_id.format(-line.amount_residual),
                                         p=line.partner_id.name, d=line.date)))
        return res

    def _check_unusual_adjustment(self, control):
        res = []
        moves = self.env['account.move'].search([
            ('move_type', '=', 'out_refund'), ('state', '=', 'posted'), ('partner_id.re_is_tenant', '=', True),
            ('re_deposit_id', '=', False), ('re_approval_state', 'not in', ('approved', 'not_required')),
            ('amount_total_signed', '<=', -abs(control.threshold_amount or 0.0))])
        for move in moves:
            lease = move.re_lease_id
            res.append(self._finding('move:%s' % move.id, move, property=lease.property_id or move.re_property_id,
                                     company=move.company_id, lease=lease, partner=move.partner_id,
                                     amount=abs(move.amount_total_signed), description=_(
                                         'Credit note %(m)s (%(amt)s) to tenant %(p)s was posted without adjustment '
                                         'approval.', m=move.name, amt=move.currency_id.format(move.amount_total),
                                         p=move.partner_id.name)))
        # manual journal entries on tenant receivables (not payments / bank lines)
        lines = self.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted'),
            ('partner_id.re_is_tenant', '=', True), ('move_id.move_type', '=', 'entry'),
            ('move_id.origin_payment_id', '=', False), ('move_id.statement_line_id', '=', False),
            ('move_id.journal_id.type', '=', 'general'), ('move_id.reversed_entry_id', '=', False),
            ('move_id.tax_cash_basis_origin_move_id', '=', False)])
        for line in lines:
            if line.move_id.journal_id == line.company_id.currency_exchange_journal_id:
                continue
            res.append(self._finding('aml:%s' % line.id, line.move_id, company=line.company_id,
                                     partner=line.partner_id, amount=abs(line.balance), description=_(
                                         'Manual journal entry %(m)s adjusts tenant %(p)s receivable by %(amt)s.',
                                         m=line.move_id.name, p=line.partner_id.name,
                                         amt=line.company_currency_id.format(line.balance))))
        return res

    def _check_refund_unapproved(self, control):
        res = []
        payments = self.env['account.payment'].search([('payment_type', '=', 'outbound'),
                                                       ('partner_type', '=', 'customer'),
                                                       ('state', 'in', ('in_process', 'paid')),
                                                       ('partner_id.re_is_tenant', '=', True)])
        for pay in payments:
            refunds = pay.reconciled_invoice_ids.filtered(lambda m: m.move_type == 'out_refund')
            approved = refunds.filtered(lambda m: m.re_approval_state in ('approved', 'not_required'))
            if not refunds or approved != refunds:
                res.append(self._finding('payment:%s' % pay.id, pay, company=pay.company_id, partner=pay.partner_id,
                                         amount=pay.amount, description=_(
                                             'Outbound payment %(p)s of %(amt)s to tenant %(t)s is not matched to an '
                                             'approved credit note / deposit refund.', p=pay.name,
                                             amt=pay.currency_id.format(pay.amount), t=pay.partner_id.name)))
        return res

    def _check_deposit_outstanding(self, control):
        res = []
        limit = self._today() - timedelta(days=control.threshold_days)
        deposits = self.env['re.security.deposit'].search([('state', 'in', ('draft', 'invoiced'))])
        for dep in deposits:
            if dep.lease_id.state not in LIVE:
                continue
            due = dep.invoice_id.invoice_date_due if dep.invoice_id else dep.lease_id.date_start
            if due and due <= limit:
                res.append(self._finding('deposit:%s' % dep.id, dep, property=dep.property_id, lease=dep.lease_id,
                                         amount=dep.amount - dep.received_amount, description=_(
                                             'Security deposit %(d)s (%(amt)s) for %(lease)s has %(what)s.', d=dep.name,
                                             amt=dep.currency_id.format(dep.amount), lease=dep.lease_id.name,
                                             what=_('not been invoiced') if dep.state == 'draft' else _('not been received'))))
        return res

    def _check_lease_unsigned(self, control):
        res = []
        limit = self._today() - timedelta(days=control.threshold_days)
        for lease in self.env['re.lease'].search([('state', 'in', LIVE), ('is_signed', '=', False),
                                                  ('date_start', '<=', limit)]):
            res.append(self._finding('lease:%s' % lease.id, lease, property=lease.property_id, lease=lease,
                                     description=_('Lease %s is active but no signed agreement is recorded.', lease.name)))
        return res

    def _wo_bills(self, wo):
        return wo.vendor_bill_ids.filtered(lambda m: m.state != 'cancel')

    def _check_vendor_bill_over_approved(self, control):
        res = []
        for wo in self.env['re.work.order'].search([('vendor_bill_ids', '!=', False)]):
            tol = wo.company_id.re_bill_tolerance_pct / 100.0
            billed = wo.actual_cost
            if wo.approved_budget and billed > wo.approved_budget * (1 + tol) + 0.005:
                res.append(self._finding('wo:%s' % wo.id, wo, property=wo.property_id, amount=billed - wo.approved_budget,
                                         partner=wo.contractor_id, description=_(
                                             'Work order %(wo)s: billed %(b)s exceeds approved %(a)s by more than %(t)s%%.',
                                             wo=wo.name, b=wo.currency_id.format(billed),
                                             a=wo.currency_id.format(wo.approved_budget),
                                             t=wo.company_id.re_bill_tolerance_pct)))
        return res

    def _check_unapproved_spend(self, control):
        res = []
        for wo in self.env['re.work.order'].search([('vendor_bill_ids', '!=', False)]):
            if wo.re_approval_state not in ('approved', 'not_required') and not wo.is_emergency:
                res.append(self._finding('wo:%s' % wo.id, wo, property=wo.property_id, amount=wo.actual_cost,
                                         partner=wo.contractor_id, description=_(
                                             'Vendor bills were recorded on work order %s which has no approved budget.',
                                             wo.name)))
        return res

    def _check_bill_without_po(self, control):
        res = []
        bills = self.env['account.move'].search([('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                                                 ('re_work_order_id', '!=', False)])
        for bill in bills:
            wo = bill.re_work_order_id
            if not wo.company_id.re_require_po_for_contractor:
                continue
            if not bill.invoice_line_ids.filtered('purchase_line_id') and bill.amount_total > (control.threshold_amount or 0):
                res.append(self._finding('bill:%s' % bill.id, bill, property=wo.property_id, partner=bill.partner_id,
                                         company=bill.company_id, amount=bill.amount_total, description=_(
                                             'Bill %(b)s for work order %(wo)s was recorded without a purchase order.',
                                             b=bill.name, wo=wo.name)))
        return res

    def _check_duplicate_vendor_bill(self, control):
        self.env['account.move'].flush_model()
        self.env.cr.execute("""
            SELECT array_agg(id ORDER BY id) FROM account_move
             WHERE move_type = 'in_invoice' AND state != 'cancel'
          GROUP BY company_id, commercial_partner_id, COALESCE(NULLIF(lower(trim(ref)), ''), 'amt:' || amount_total::text || ':' || COALESCE(invoice_date::text, ''))
            HAVING COUNT(*) > 1
        """)
        res = []
        for ids, in self.env.cr.fetchall():
            moves = self.env['account.move'].browse(ids)
            first = moves[0]
            prop = moves.mapped('re_work_order_id.property_id')[:1] or moves.mapped('line_ids.re_property_id')[:1]
            res.append(self._finding('bills:%s' % '-'.join(map(str, ids)), first, property=prop,
                                     company=first.company_id, partner=first.partner_id, amount=first.amount_total,
                                     description=_('Possible duplicate vendor bills from %(p)s: %(names)s (same '
                                                   'reference or same amount and date).', p=first.partner_id.name,
                                                   names=', '.join(m.name or str(m.id) for m in moves))))
        return res

    def _check_missing_analytic(self, control):
        res = []
        bills = self.env['account.move'].search([('move_type', 'in', ('in_invoice', 'in_refund')), ('state', '=', 'posted'),
                                                 '|', ('re_work_order_id', '!=', False),
                                                 ('invoice_line_ids.purchase_line_id.order_id.re_property_id', '!=', False)])
        for bill in bills:
            lines = bill.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and not l.re_property_id)
            if lines:
                prop = bill.re_work_order_id.property_id or \
                    bill.invoice_line_ids.purchase_line_id.order_id.re_property_id[:1]
                res.append(self._finding('bill:%s' % bill.id, bill, property=prop, company=bill.company_id,
                                         partner=bill.partner_id, amount=sum(lines.mapped('balance')), description=_(
                                             'Bill %(b)s has %(n)s line(s) without property analytic allocation; the cost '
                                             'is missing from property profitability.', b=bill.name, n=len(lines))))
        return res

    def _check_wrong_property_allocation(self, control):
        res = []
        bills = self.env['account.move'].search([('move_type', 'in', ('in_invoice', 'in_refund')),
                                                 ('state', '=', 'posted'), ('re_work_order_id', '!=', False)])
        for bill in bills:
            prop = bill.re_work_order_id.property_id
            wrong = bill.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.re_property_id and l.re_property_id != prop)
            if wrong:
                res.append(self._finding('bill:%s' % bill.id, bill, property=prop, company=bill.company_id,
                                         partner=bill.partner_id, amount=sum(wrong.mapped('balance')), description=_(
                                             'Bill %(b)s relates to work order %(wo)s (%(p)s) but is allocated to %(o)s.',
                                             b=bill.name, wo=bill.re_work_order_id.name, p=prop.display_name,
                                             o=', '.join(wrong.mapped('re_property_id.display_name')))))
        return res

    def _check_service_charge_overrun(self, control):
        res = []
        pct = control.threshold_pct or 5.0
        for budget in self.env['re.service.charge.budget'].search([('state', 'in', ('approved', 'applied', 'reconciled'))]):
            if budget.total_budget and budget.variance_pct > pct:
                res.append(self._finding('budget:%s' % budget.id, budget, property=budget.property_id,
                                         building=budget.building_id, amount=budget.variance, description=_(
                                             'Service-charge budget %(b)s: actual %(a)s exceeds budget %(t)s by %(p).1f%%.',
                                             b=budget.name, a=budget.currency_id.format(budget.total_actual),
                                             t=budget.currency_id.format(budget.total_budget), p=budget.variance_pct)))
        return res

    def _check_service_charge_unreconciled(self, control):
        res = []
        limit = self._today() - timedelta(days=control.threshold_days or 90)
        for budget in self.env['re.service.charge.budget'].search([('state', '=', 'applied'), ('date_to', '<', limit)]):
            res.append(self._finding('budget:%s' % budget.id, budget, property=budget.property_id,
                                     building=budget.building_id, description=_(
                                         'Service-charge period %(b)s ended on %(d)s and has not been reconciled with '
                                         'tenants.', b=budget.name, d=budget.date_to)))
        return res

    def _check_emergency_not_reviewed(self, control):
        res = []
        limit = fields.Datetime.now() - timedelta(days=control.threshold_days or 3)
        for wo in self.env['re.work.order'].search([('is_emergency', '=', True),
                                                    ('emergency_review_state', '=', 'pending'),
                                                    ('emergency_started', '<=', limit)]):
            res.append(self._finding('wo:%s' % wo.id, wo, property=wo.property_id, amount=wo.estimated_cost,
                                     description=_('Emergency work order %s started without prior approval and has not '
                                                   'been reviewed.', wo.name)))
        return res

    def _check_contractor_non_compliant(self, control):
        res = []
        open_wos = self.env['re.work.order'].search([('contractor_id', '!=', False),
                                                     ('state', 'in', ('assigned', 'in_progress', 'pending'))])
        for wo in open_wos:
            partner = wo.contractor_id.commercial_partner_id
            if not partner.re_is_compliant:
                res.append(self._finding('wo:%s' % wo.id, wo, property=wo.property_id, partner=partner, description=_(
                    'Contractor %(c)s on work order %(wo)s is not compliant: %(why)s', c=partner.name, wo=wo.name,
                    why=partner.re_compliance_note)))
        return res

    def _check_insurance_expiry(self, control):
        res = []
        limit = self._today() + timedelta(days=control.threshold_days or 30)
        for prop in self.env['re.property'].search([('state', '!=', 'disposed'), ('insurance_expiry', '!=', False),
                                                    ('insurance_expiry', '<=', limit)]):
            res.append(self._finding('property:%s' % prop.id, prop, property=prop,
                                     description=_('Insurance policy %(p)s for %(prop)s expires on %(d)s.',
                                                   p=prop.insurance_policy or '-', prop=prop.display_name,
                                                   d=prop.insurance_expiry)))
        return res
