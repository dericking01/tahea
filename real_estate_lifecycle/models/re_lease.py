# -*- coding: utf-8 -*-
import calendar
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

FREQUENCY_MONTHS = {'monthly': 1, 'quarterly': 3, 'semi_annual': 6, 'annual': 12}
OCCUPYING_STATES = ('to_approve', 'approved', 'active', 'expiring')
LIVE_STATES = ('active', 'expiring')
CHARGE_TYPES = [
    ('service_charge', 'Service Charge'),
    ('parking', 'Parking'),
    ('marketing_levy', 'Marketing Levy'),
    ('utility_fixed', 'Fixed Utility Charge'),
    ('other', 'Other Contractual Fee'),
    ('concession', 'Rent Concession (negative)'),
]
# Fields that define the commercial terms. After submission they can only be
# changed through an approved amendment (audit + segregation of duties).
RESTRICTED_FIELDS = {
    'tenant_id', 'unit_ids', 'date_start', 'date_end', 'rent_amount', 'currency_id', 'billing_frequency',
    'billing_anchor', 'rent_free_date_from', 'rent_free_date_to', 'rent_free_includes_charges', 'deposit_amount',
    'turnover_rent_enabled', 'turnover_rate', 'turnover_breakpoint', 'turnover_mode', 'property_id',
}


def _month_end(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


class ReLease(models.Model):
    _name = 're.lease'
    _description = 'Lease Agreement'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin', 'portal.mixin']
    _order = 'date_start desc, id desc'
    _re_approval_document_type = 'lease'

    name = fields.Char('Lease Reference', required=True, copy=False, readonly=True, default='/', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('expiring', 'Expiring'),
        ('renewed', 'Renewed'),
        ('terminated', 'Terminated'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    active = fields.Boolean(default=True)

    tenant_id = fields.Many2one('res.partner', 'Tenant', required=True, tracking=True, index=True)
    joint_tenant_ids = fields.Many2many('res.partner', 're_lease_joint_tenant_rel', 'lease_id', 'partner_id',
                                        string='Joint Tenants / Guarantors')
    lease_type_id = fields.Many2one('re.lease.type', 'Lease Type', required=True, tracking=True)
    lease_category = fields.Selection(related='lease_type_id.category', store=True)
    property_id = fields.Many2one('re.property', required=True, tracking=True, index=True)
    building_id = fields.Many2one('re.building', domain="[('property_id', '=', property_id)]", tracking=True)
    unit_ids = fields.Many2many('re.unit', 're_lease_unit_rel', 'lease_id', 'unit_id', string='Units / Spaces',
                                domain="[('property_id', '=', property_id)]")
    leased_area_sqm = fields.Float('Leased Area (m²)', compute='_compute_leased_area', store=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    manager_id = fields.Many2one(related='property_id.manager_id', store=True, string='Property Manager')
    portfolio_id = fields.Many2one(related='property_id.portfolio_id', store=True)
    currency_id = fields.Many2one('res.currency', required=True, tracking=True,
                                  default=lambda self: self.env.company.currency_id)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Company Currency')
    user_id = fields.Many2one('res.users', 'Leasing Officer', default=lambda self: self.env.user, tracking=True)
    crm_lead_id = fields.Many2one('crm.lead', 'Originating Opportunity', copy=False)

    # ---- Term ---------------------------------------------------------------------------
    date_start = fields.Date('Start Date', required=True, tracking=True)
    date_end = fields.Date('End Date', required=True, tracking=True)
    termination_date = fields.Date(tracking=True, copy=False)
    effective_end_date = fields.Date(compute='_compute_effective_end', store=True)
    move_in_date = fields.Date(copy=False, tracking=True)
    move_out_date = fields.Date(copy=False, tracking=True)
    duration_months = fields.Integer(compute='_compute_duration')
    days_to_expiry = fields.Integer(compute='_compute_days_to_expiry')
    notice_period_days = fields.Integer('Notice Period (days)', default=90)
    break_clause_date = fields.Date('Break Option Date')
    break_clause_terms = fields.Text('Break Clause')
    renewal_terms = fields.Text()
    termination_conditions = fields.Text()
    termination_type = fields.Selection([
        ('natural', 'End of Term'), ('early_tenant', 'Early - Tenant Request'),
        ('early_landlord', 'Early - Landlord (default / breach)'), ('mutual', 'Mutual Agreement'),
        ('break_clause', 'Break Clause Exercised')], copy=False, tracking=True)
    termination_reason = fields.Text(copy=False)
    parent_lease_id = fields.Many2one('re.lease', 'Renewal Of', copy=False, readonly=True)
    renewal_lease_ids = fields.One2many('re.lease', 'parent_lease_id', 'Renewals')

    # ---- Financial terms ----------------------------------------------------------------
    rent_amount = fields.Monetary('Base Monthly Rent', required=True, tracking=True,
                                  help='Contractual base rent per month before escalations. For multi-unit leases '
                                       'this is the total for all units.')
    current_rent = fields.Monetary('Current Monthly Rent', compute='_compute_current_rent')
    billing_frequency = fields.Selection([
        ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('semi_annual', 'Semi-annual'), ('annual', 'Annual')],
        required=True, default='monthly', tracking=True)
    billing_anchor = fields.Selection([
        ('calendar', 'Calendar periods (pro-rated first period)'),
        ('lease_start', 'Lease anniversary periods')], default='calendar', required=True)
    invoice_advance_days = fields.Integer('Invoice Days in Advance', default=0,
                                          help='Invoices are dated this many days before the billing period starts.')
    payment_term_id = fields.Many2one('account.payment.term', tracking=True)
    payment_due_days = fields.Integer('Due Days (if no payment term)', default=7)
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Fiscal Position / Tax Treatment',
                                         check_company=True)
    rent_free_date_from = fields.Date('Rent-free From')
    rent_free_date_to = fields.Date('Rent-free To')
    rent_free_includes_charges = fields.Boolean('Rent-free also waives other charges')
    deposit_amount = fields.Monetary('Security Deposit Required', tracking=True)
    service_charge_applicable = fields.Boolean('Service Charge Obligation', default=True)
    utility_recharge = fields.Boolean('Utility Consumption Recharged', default=False,
                                      help='Metered consumption of the leased units is billed to the tenant.')
    turnover_rent_enabled = fields.Boolean('Turnover Rent')
    turnover_rate = fields.Float('Turnover Rate (%)')
    turnover_breakpoint = fields.Monetary('Turnover Breakpoint (per period)',
                                          help='Turnover rent applies only on gross sales above this amount.')
    turnover_mode = fields.Selection([
        ('greater_of', 'Greater of base rent (minimum guaranteed) or % of sales'),
        ('additional', 'Base rent plus % of sales'),
    ], default='greater_of')

    escalation_ids = fields.One2many('re.lease.escalation', 'lease_id', copy=True)
    charge_ids = fields.One2many('re.lease.charge', 'lease_id', copy=True)
    amendment_ids = fields.One2many('re.lease.amendment', 'lease_id')
    schedule_ids = fields.One2many('re.billing.schedule', 'lease_id')
    deposit_ids = fields.One2many('re.security.deposit', 'lease_id')
    turnover_report_ids = fields.One2many('re.turnover.report', 'lease_id')

    # ---- Documents --------------------------------------------------------------------------
    is_signed = fields.Boolean('Agreement Signed', copy=False, tracking=True)
    signed_date = fields.Date(copy=False)
    signed_attachment_id = fields.Many2one('ir.attachment', 'Signed Agreement', copy=False,
                                           domain="[('res_model', '=', 're.lease'), ('res_id', '=', id)]")
    note = fields.Html()
    alert_last_threshold = fields.Integer(copy=False)

    # ---- Financial summary (from native accounting) ----------------------------------------
    invoice_count = fields.Integer(compute='_compute_financials')
    amount_invoiced = fields.Monetary(compute='_compute_financials', currency_field='company_currency_id')
    amount_due = fields.Monetary('Outstanding Balance', compute='_compute_financials',
                                 currency_field='company_currency_id')
    deposit_held = fields.Monetary(compute='_compute_financials', currency_field='company_currency_id')
    next_invoice_date = fields.Date(compute='_compute_next_invoice')

    _sql_constraints = [
        ('dates_check', 'CHECK(date_end >= date_start)', 'The lease end date must be after the start date.'),
    ]

    # ------------------------------------------------------------------------------------------
    @api.depends('unit_ids.area_sqm')
    def _compute_leased_area(self):
        for rec in self:
            rec.leased_area_sqm = sum(rec.unit_ids.mapped('area_sqm'))

    @api.depends('date_end', 'termination_date')
    def _compute_effective_end(self):
        for rec in self:
            rec.effective_end_date = rec.termination_date or rec.date_end

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                delta = relativedelta(rec.date_end + timedelta(days=1), rec.date_start)
                rec.duration_months = delta.years * 12 + delta.months
            else:
                rec.duration_months = 0

    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_expiry = (rec.effective_end_date - today).days if rec.effective_end_date else 0

    def _compute_current_rent(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.current_rent = rec._get_rent_rate(today) if rec.date_start else rec.rent_amount

    def _compute_financials(self):
        Move = self.env['account.move'].sudo()
        for rec in self:
            moves = Move.search([('re_lease_id', '=', rec.id), ('state', '=', 'posted'),
                                 ('move_type', 'in', ('out_invoice', 'out_refund'))])
            rental = moves.filtered(lambda m: not m.re_deposit_id)
            rec.invoice_count = len(Move.search([('re_lease_id', '=', rec.id)]))
            rec.amount_invoiced = sum(rental.mapped('amount_untaxed_signed'))
            rec.amount_due = sum(moves.mapped('amount_residual_signed'))
            rec.deposit_held = sum(rec.deposit_ids.mapped('held_amount'))

    def _compute_next_invoice(self):
        for rec in self:
            pending = rec.schedule_ids.filtered(lambda s: s.state == 'pending').sorted('invoice_date')[:1]
            rec.next_invoice_date = pending.invoice_date

    # ------------------------------------------------------------------------------------------
    @api.onchange('lease_type_id')
    def _onchange_lease_type(self):
        if self.lease_type_id:
            self.billing_frequency = self.lease_type_id.default_billing_frequency or self.billing_frequency
            self.notice_period_days = self.lease_type_id.default_notice_days
            if self.lease_type_id.fiscal_position_id:
                self.fiscal_position_id = self.lease_type_id.fiscal_position_id

    @api.onchange('unit_ids')
    def _onchange_units(self):
        if self.unit_ids and not self.rent_amount:
            self.rent_amount = sum(self.unit_ids.mapped('market_rent'))
        if self.unit_ids and not self.building_id:
            self.building_id = self.unit_ids[:1].building_id

    @api.onchange('rent_amount', 'lease_type_id')
    def _onchange_deposit(self):
        if self.rent_amount and not self.deposit_amount and self.lease_type_id:
            self.deposit_amount = self.rent_amount * self.lease_type_id.default_deposit_months

    @api.constrains('unit_ids', 'state', 'date_start', 'date_end', 'termination_date')
    def _check_overlap(self):
        for rec in self.filtered(lambda l: l.state in OCCUPYING_STATES):
            for unit in rec.unit_ids.sudo():
                if unit.allow_multi_occupancy:
                    continue
                clash = self.search([
                    ('id', '!=', rec.id), ('unit_ids', 'in', unit.id), ('state', 'in', OCCUPYING_STATES),
                    ('date_start', '<=', rec.effective_end_date), ('effective_end_date', '>=', rec.date_start)],
                    limit=1)
                if clash:
                    raise ValidationError(_(
                        'Unit %(unit)s is already committed under lease %(lease)s (%(start)s - %(end)s). '
                        'Overlapping leases are only possible for units authorised for multi-occupancy.',
                        unit=unit.display_name, lease=clash.name, start=clash.date_start,
                        end=clash.effective_end_date))

    @api.constrains('unit_ids', 'property_id', 'building_id')
    def _check_units(self):
        for rec in self:
            if rec.unit_ids.filtered(lambda u: u.property_id != rec.property_id):
                raise ValidationError(_('All leased units must belong to property %s.', rec.property_id.display_name))
            if rec.building_id and rec.building_id.property_id != rec.property_id:
                raise ValidationError(_('The building does not belong to the property.'))
            if rec.unit_ids.filtered(lambda u: not u.is_lettable):
                raise ValidationError(_('Non-rentable units cannot be leased.'))

    @api.constrains('rent_free_date_from', 'rent_free_date_to', 'turnover_rate')
    def _check_terms(self):
        for rec in self:
            if bool(rec.rent_free_date_from) != bool(rec.rent_free_date_to):
                raise ValidationError(_('Set both the rent-free start and end dates.'))
            if rec.rent_free_date_from and rec.rent_free_date_to < rec.rent_free_date_from:
                raise ValidationError(_('Rent-free end must be after rent-free start.'))
            if rec.turnover_rate < 0 or rec.turnover_rate > 100:
                raise ValidationError(_('Turnover rate must be between 0 and 100%.'))

    # ------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.lease') or '/'
        records = super().create(vals_list)
        records.mapped('tenant_id').sudo().write({'re_is_tenant': True})
        return records

    def write(self, vals):
        if not self.env.context.get('re_lease_amendment_apply'):
            touched = RESTRICTED_FIELDS & set(vals)
            if touched:
                locked = self.filtered(lambda l: l.state != 'draft')
                if locked:
                    labels = ', '.join(self._fields[f].string for f in touched)
                    raise UserError(_(
                        'Lease %(lease)s is %(state)s. Commercial terms (%(fields)s) can only be changed through '
                        'an approved lease amendment.', lease=locked[0].name,
                        state=dict(self._fields['state'].selection)[locked[0].state], fields=labels))
        res = super().write(vals)
        if 'tenant_id' in vals:
            self.mapped('tenant_id').sudo().write({'re_is_tenant': True})
        return res

    def unlink(self):
        if self.filtered(lambda l: l.state not in ('draft', 'cancelled')):
            raise UserError(_('Only draft or cancelled leases can be deleted. Archive the lease instead.'))
        return super().unlink()

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/leases/%s' % rec.id

    def _re_approval_amount(self):
        rate = self.currency_id._convert(self.rent_amount * 12, self.company_id.currency_id, self.company_id,
                                         self.date_start or fields.Date.context_today(self))
        return rate

    # ------------------------------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft leases can be submitted.'))
            if not rec.unit_ids:
                raise UserError(_('Select at least one unit, space or plot for lease %s.', rec.name))
            if rec.rent_amount < 0:
                raise UserError(_('Rent cannot be negative.'))
            rec.state = 'to_approve'
            if rec._re_request_approval():
                rec._re_on_approved()
            rec.message_post(body=_('Lease submitted for approval.'))

    def action_approve(self):
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Lease %s is not waiting for approval.', rec.name))
        self._re_approve()
        self._re_on_approved()

    def _re_on_approved(self):
        for rec in self:
            rec.state = 'approved'
            # contractual escalations captured in the approved lease are approved with it
            rec.escalation_ids.filtered(lambda e: e.state in ('draft', 'to_approve')).write({
                'state': 'approved', 'contractual': True})
            rec.message_post(body=_('Lease approved. Escalations agreed in the contract were approved with it.'))

    def _re_after_reject(self):
        self.write({'state': 'draft'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('to_approve', 'approved', 'cancelled'):
                raise UserError(_('Only leases that are not yet active can be reset to draft.'))
            if rec.schedule_ids.filtered(lambda s: s.state == 'invoiced'):
                raise UserError(_('Lease %s already has invoices.', rec.name))
            rec.schedule_ids.unlink()
            rec._re_log('reset', note=_('Reset to draft'))
        self.write({'state': 'draft', 're_approval_state': 'none'})

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'to_approve', 'approved'):
                raise UserError(_('Active leases must be terminated, not cancelled.'))
            rec.schedule_ids.filtered(lambda s: s.state != 'invoiced').unlink()
        self.write({'state': 'cancelled'})

    def action_activate(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Lease %s must be approved before activation.', rec.name))
            rec.write({'state': 'active', 'move_in_date': rec.move_in_date or rec.date_start})
            rec.unit_ids.write({'occupancy_status': 'occupied'})
            rec.unit_ids.filtered(lambda u: u.is_plot).write({'plot_status': 'leased'})
            if rec.parent_lease_id and rec.parent_lease_id.state in LIVE_STATES + ('expired',):
                rec.parent_lease_id.write({'state': 'renewed'})
                rec.parent_lease_id.message_post(body=_('Renewed by lease %s.', rec.name))
            if rec.deposit_amount and not rec.deposit_ids:
                self.env['re.security.deposit'].create({
                    'lease_id': rec.id, 'amount': rec.deposit_amount, 'currency_id': rec.currency_id.id,
                    'purpose': 'security'})
            rec._re_generate_schedule()
            if rec.date_end and (rec.date_end - today).days <= rec.company_id.re_expiring_days:
                rec.state = 'expiring'
            rec.message_post(body=_('Lease activated; units marked occupied and billing schedule generated.'))

    def action_mark_signed(self):
        for rec in self:
            attachment = rec.signed_attachment_id or self.env['ir.attachment'].search(
                [('res_model', '=', 're.lease'), ('res_id', '=', rec.id)], order='id desc', limit=1)
            if not attachment:
                raise UserError(_('Attach the signed agreement to lease %s (chatter attachment) first.', rec.name))
            rec.write({'is_signed': True, 'signed_attachment_id': attachment.id,
                       'signed_date': rec.signed_date or fields.Date.context_today(self)})

    def action_open_terminate_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Terminate Lease'), 'res_model': 're.lease.terminate.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_lease_id': self.id},
        }

    def action_open_renew_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Renew Lease'), 'res_model': 're.lease.renew.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_lease_id': self.id},
        }

    def _re_terminate(self, termination_date, termination_type, reason, vacate=True):
        """Early/natural termination. Posted invoices are never modified: invoices
        covering periods after the termination date are flagged for credit-note review."""
        for rec in self:
            if rec.state not in LIVE_STATES + ('approved',):
                raise UserError(_('Only approved or active leases can be terminated.'))
            if termination_date < rec.date_start:
                raise UserError(_('Termination date cannot be before the lease start.'))
            rec.with_context(re_lease_amendment_apply=True).write({
                'termination_date': min(termination_date, rec.date_end),
                'termination_type': termination_type,
                'termination_reason': reason,
                'state': 'terminated',
            })
            rec._re_generate_schedule()
            over_billed = rec.schedule_ids.filtered(
                lambda s: s.state == 'invoiced' and s.period_end > rec.effective_end_date)
            for line in over_billed:
                self.env['re.exception']._re_raise(
                    'termination_overbilled', line, rec.company_id,
                    _('Lease %(lease)s terminated on %(date)s but %(inv)s bills period %(p1)s - %(p2)s. Review and '
                      'issue a credit note if appropriate.', lease=rec.name, date=rec.effective_end_date,
                      inv=line.invoice_id.name or line.invoice_id.display_name, p1=line.period_start,
                      p2=line.period_end),
                    lease=rec)
            if vacate:
                rec._re_vacate_units(termination_date)
            rec.message_post(body=_('Lease terminated (%(type)s) effective %(date)s. %(reason)s',
                                    type=dict(self._fields['termination_type'].selection).get(termination_type),
                                    date=termination_date, reason=reason or ''))

    def _re_vacate_units(self, move_out_date=None):
        for rec in self:
            rec.move_out_date = move_out_date or fields.Date.context_today(self)
            other_live = self.search([('id', '!=', rec.id), ('state', 'in', LIVE_STATES),
                                      ('unit_ids', 'in', rec.unit_ids.ids)])
            units = rec.unit_ids - other_live.mapped('unit_ids')
            units.write({'occupancy_status': 'vacant', 'vacant_since': rec.move_out_date})
            units.filtered(lambda u: u.is_plot).write({'plot_status': 'available'})

    def action_record_move_out(self):
        for rec in self:
            if rec.state not in ('expired', 'terminated'):
                raise UserError(_('Record move-out only for expired or terminated leases.'))
            rec._re_vacate_units()

    def action_generate_annual_escalations(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Annual escalations can only be generated on draft leases. '
                                  'Use an amendment for active leases.'))
            pct = self.env.context.get('escalation_pct') or 5.0
            d = rec.date_start + relativedelta(years=1)
            existing = set(rec.escalation_ids.mapped('effective_date'))
            while d <= rec.date_end:
                if d not in existing:
                    self.env['re.lease.escalation'].create({
                        'lease_id': rec.id, 'effective_date': d, 'method': 'percent', 'value': pct})
                d += relativedelta(years=1)

    # ------------------------------------------------------------------------------------------
    # Rent computation
    # ------------------------------------------------------------------------------------------
    def _effective_escalations(self):
        self.ensure_one()
        return self.escalation_ids.filtered(lambda e: e.state in ('approved', 'applied')).sorted(
            lambda e: (e.effective_date, e.id))

    def _get_rent_rate(self, on_date):
        """Monthly rent rate applicable on a date: base rent compounded with all approved
        escalations effective on or before that date (rent-free is applied separately)."""
        self.ensure_one()
        rate = self.rent_amount
        for esc in self._effective_escalations():
            if esc.effective_date > on_date:
                break
            rate = esc._apply(rate)
        return rate

    def _is_rent_free(self, on_date):
        self.ensure_one()
        return bool(self.rent_free_date_from and self.rent_free_date_from <= on_date <= self.rent_free_date_to)

    def _get_billing_periods(self, horizon_end):
        """List of (period_start, period_end) from the lease start up to the effective end
        (or horizon_end if earlier). Periods are deterministic so schedule generation is idempotent."""
        self.ensure_one()
        months = FREQUENCY_MONTHS[self.billing_frequency]
        end = min(self.effective_end_date, horizon_end) if horizon_end else self.effective_end_date
        periods = []
        start = self.date_start
        if self.billing_anchor == 'calendar' and start.day != 1:
            first_boundary = start.replace(day=1) + relativedelta(months=1)
            periods.append((start, min(first_boundary - timedelta(days=1), self.effective_end_date)))
            cursor = first_boundary
        else:
            cursor = start
        anchor = cursor
        n = 0
        while cursor <= self.effective_end_date and cursor <= end:
            p_end = anchor + relativedelta(months=months * (n + 1)) - timedelta(days=1)
            periods.append((cursor, min(p_end, self.effective_end_date)))
            n += 1
            cursor = anchor + relativedelta(months=months * n)
        return [p for p in periods if p[0] <= end]

    def _segments(self, p_start, p_end, extra_breaks=()):
        """Split a period at month boundaries and at the given break dates.
        Yields (seg_start, seg_end, month_fraction)."""
        breaks = set(d for d in extra_breaks if d and p_start < d <= p_end)
        cur = p_start
        while cur <= p_end:
            seg_end = min(_month_end(cur), p_end)
            nxt = sorted(b for b in breaks if cur < b <= seg_end)
            if nxt:
                seg_end = nxt[0] - timedelta(days=1)
            days_in_month = calendar.monthrange(cur.year, cur.month)[1]
            yield cur, seg_end, ((seg_end - cur).days + 1) / days_in_month
            cur = seg_end + timedelta(days=1)

    def _compute_rent_for_period(self, p_start, p_end):
        self.ensure_one()
        breaks = [e.effective_date for e in self._effective_escalations()]
        if self.rent_free_date_from:
            breaks += [self.rent_free_date_from, self.rent_free_date_to + timedelta(days=1)]
        amount = 0.0
        notes = []
        for s, e, frac in self._segments(p_start, p_end, breaks):
            if self._is_rent_free(s):
                notes.append(_('%(s)s-%(e)s rent-free', s=s, e=e))
                continue
            rate = self._get_rent_rate(s)
            amount += rate * frac
            notes.append('%s-%s: %s x %.4f' % (s, e, self.currency_id.format(rate), frac))
        return self.currency_id.round(amount), '; '.join(notes)

    def _compute_charge_for_period(self, charge, p_start, p_end):
        self.ensure_one()
        breaks = [charge.date_from, charge.date_to and charge.date_to + timedelta(days=1)]
        if self.rent_free_includes_charges and self.rent_free_date_from:
            breaks += [self.rent_free_date_from, self.rent_free_date_to + timedelta(days=1)]
        amount = 0.0
        notes = []
        for s, e, frac in self._segments(p_start, p_end, breaks):
            if charge.date_from and s < charge.date_from or charge.date_to and s > charge.date_to:
                continue
            if self.rent_free_includes_charges and self._is_rent_free(s) and charge.charge_type != 'concession':
                notes.append(_('%(s)s-%(e)s waived (rent-free)', s=s, e=e))
                continue
            amount += charge.amount * frac
            notes.append('%s-%s: %s x %.4f' % (s, e, self.currency_id.format(charge.amount), frac))
        return self.currency_id.round(amount), '; '.join(notes)

    def _schedule_horizon(self):
        return fields.Date.context_today(self) + relativedelta(months=24)

    def _re_expected_schedule(self):
        self.ensure_one()
        expected = {}
        for p_start, p_end in self._get_billing_periods(self._schedule_horizon()):
            inv_date = p_start - timedelta(days=self.invoice_advance_days or 0)
            amount, note = self._compute_rent_for_period(p_start, p_end)
            expected[('rent', p_start)] = {
                'charge_type': 'rent', 'charge_id': False, 'period_end': p_end, 'invoice_date': inv_date,
                'amount': amount, 'explanation': note, 'name': _('Rent %(s)s to %(e)s', s=p_start, e=p_end)}
            for charge in self.charge_ids.filtered('active'):
                if charge.date_from and charge.date_from > p_end or charge.date_to and charge.date_to < p_start:
                    continue
                amount, note = self._compute_charge_for_period(charge, p_start, p_end)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                expected[('charge_%s' % charge.id, p_start)] = {
                    'charge_type': charge.charge_type, 'charge_id': charge.id, 'period_end': p_end,
                    'invoice_date': inv_date, 'amount': amount, 'explanation': note,
                    'service_charge_budget_id': charge.service_charge_budget_id.id,
                    'name': '%s %s to %s' % (charge.name, p_start, p_end)}
        return expected

    def _re_generate_schedule(self):
        """Create / refresh billing schedule lines. Invoiced lines are never touched
        (historical billing preserved); pending lines are recomputed; obsolete pending
        lines are removed. Safe to run any number of times."""
        Schedule = self.env['re.billing.schedule']
        for rec in self:
            if rec.state not in LIVE_STATES + ('terminated', 'expired', 'renewed'):
                continue
            expected = rec._re_expected_schedule()
            existing = {(l.obligation_key, l.period_start): l for l in rec.schedule_ids}
            to_create = []
            for key, vals in expected.items():
                line = existing.pop(key, None)
                if line:
                    if line.state == 'invoiced':
                        continue
                    upd = {}
                    for fname, value in vals.items():
                        current = line[fname]
                        if isinstance(current, models.BaseModel):
                            current, value = current.id or False, value or False
                        elif isinstance(current, float):
                            if rec.currency_id.compare_amounts(current, value or 0.0) == 0:
                                continue
                        if current != value:
                            upd[fname] = value
                    if upd:
                        line.write(upd)
                else:
                    to_create.append(dict(vals, lease_id=rec.id, obligation_key=key[0], period_start=key[1]))
            if to_create:
                Schedule.create(to_create)
            obsolete = Schedule.browse([l.id for l in existing.values() if l.state != 'invoiced'])
            obsolete.unlink()

    # ------------------------------------------------------------------------------------------
    def action_generate_due_invoices(self):
        self._re_generate_schedule()
        lines = self.schedule_ids.filtered(
            lambda s: s.state == 'pending' and s.invoice_date <= fields.Date.context_today(self))
        moves = lines._re_create_invoices()
        if not moves:
            raise UserError(_('Nothing is due for invoicing.'))
        return self._action_view_moves(moves)

    def _action_view_moves(self, moves):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', moves.ids)]
        action['context'] = {'default_move_type': 'out_invoice'}
        return action

    def action_view_invoices(self):
        self.ensure_one()
        moves = self.env['account.move'].search([('re_lease_id', '=', self.id)])
        return self._action_view_moves(moves)

    def action_view_schedule(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_billing_schedule')
        action['domain'] = [('lease_id', '=', self.id)]
        action['context'] = {'search_default_group_period': 0}
        return action

    def action_new_amendment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Lease Amendment'), 'res_model': 're.lease.amendment',
            'view_mode': 'form', 'target': 'current',
            'context': {'default_lease_id': self.id, 'default_new_rent_amount': self.current_rent,
                        'default_new_date_end': self.date_end},
        }

    # ------------------------------------------------------------------------------------------
    # Scheduled jobs
    # ------------------------------------------------------------------------------------------
    @api.model
    def _cron_lease_lifecycle(self):
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            Lease = self.with_company(company).sudo()
            # active -> expiring
            window = today + timedelta(days=company.re_expiring_days)
            Lease.search([('company_id', '=', company.id), ('state', '=', 'active'),
                          ('effective_end_date', '<=', window)]).write({'state': 'expiring'})
            # active/expiring -> expired
            ended = Lease.search([('company_id', '=', company.id), ('state', 'in', LIVE_STATES),
                                  ('effective_end_date', '<', today)])
            for lease in ended:
                lease.state = 'expired'
                lease.message_post(body=_('Lease expired on %s. Record move-out or renew.', lease.effective_end_date))
            # expiry alerts at configurable thresholds (e.g. 120/90/60/30 days)
            thresholds = company._re_alert_days()
            for lease in Lease.search([('company_id', '=', company.id), ('state', 'in', LIVE_STATES)]):
                days = (lease.effective_end_date - today).days
                due = [t for t in thresholds if days <= t]
                if not due:
                    continue
                threshold = min(due)
                if lease.alert_last_threshold and lease.alert_last_threshold <= threshold:
                    continue
                lease.alert_last_threshold = threshold
                lease.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=today,
                    user_id=(lease.user_id or lease.manager_id or self.env.user).id,
                    summary=_('Lease expires in %s days', days),
                    note=_('Lease %(lease)s for %(tenant)s ends on %(date)s. Decide on renewal or vacation '
                           '(notice period %(notice)s days).', lease=lease.name, tenant=lease.tenant_id.name,
                           date=lease.effective_end_date, notice=lease.notice_period_days))
            # upcoming escalations (30 days) -> reminder
            soon = today + timedelta(days=30)
            for esc in self.env['re.lease.escalation'].sudo().search([
                    ('lease_id.company_id', '=', company.id), ('lease_id.state', 'in', LIVE_STATES),
                    ('effective_date', '>=', today), ('effective_date', '<=', soon), ('reminder_sent', '=', False)]):
                esc.lease_id.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=esc.effective_date,
                    user_id=(esc.lease_id.user_id or esc.lease_id.manager_id or self.env.user).id,
                    summary=_('Rent escalation on %s', esc.effective_date),
                    note=_('%(desc)s. Status: %(state)s.', desc=esc.display_name,
                           state=dict(esc._fields['state'].selection)[esc.state]))
                esc.reminder_sent = True
            # approved escalations whose date passed are marked applied
            self.env['re.lease.escalation'].sudo().search([
                ('lease_id.company_id', '=', company.id), ('state', '=', 'approved'),
                ('effective_date', '<=', today)]).write({'state': 'applied'})


class ReLeaseCharge(models.Model):
    _name = 're.lease.charge'
    _description = 'Lease Contractual Charge'
    _order = 'lease_id, charge_type, id'

    lease_id = fields.Many2one('re.lease', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    charge_type = fields.Selection(CHARGE_TYPES, required=True, default='service_charge')
    name = fields.Char('Description', required=True)
    amount = fields.Monetary('Monthly Amount', required=True,
                             help='Amount per month; billed per the lease billing frequency and pro-rated for '
                                  'partial periods. Concessions are entered as negative amounts.')
    date_from = fields.Date()
    date_to = fields.Date()
    active = fields.Boolean(default=True)
    service_charge_budget_id = fields.Many2one('re.service.charge.budget', readonly=True, copy=False)
    service_charge_allocation_id = fields.Many2one('re.service.charge.allocation', readonly=True, copy=False,
                                                   ondelete='set null')

    @api.onchange('charge_type')
    def _onchange_charge_type(self):
        if self.charge_type and not self.name:
            self.name = dict(CHARGE_TYPES)[self.charge_type]

    @api.constrains('amount', 'charge_type')
    def _check_amount(self):
        for rec in self:
            if rec.charge_type == 'concession' and rec.amount > 0:
                raise ValidationError(_('Concessions must be negative amounts.'))
            if rec.charge_type != 'concession' and rec.amount < 0:
                raise ValidationError(_('Only concessions may be negative.'))

    def _check_lease_editable(self):
        if self.env.context.get('re_lease_amendment_apply'):
            return
        if self.mapped('lease_id').filtered(lambda l: l.state != 'draft'):
            raise UserError(_('Charges of a submitted/active lease can only be changed through an approved '
                              'amendment or an approved service-charge budget.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_lease_editable()
        return records

    def write(self, vals):
        self._check_lease_editable()
        return super().write(vals)

    def unlink(self):
        self._check_lease_editable()
        return super().unlink()


class ReLeaseEscalation(models.Model):
    _name = 're.lease.escalation'
    _description = 'Rent Escalation'
    _inherit = ['mail.thread', 're.approval.mixin']
    _order = 'lease_id, effective_date'
    _re_approval_document_type = 'rent_escalation'

    lease_id = fields.Many2one('re.lease', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    effective_date = fields.Date(required=True, tracking=True)
    method = fields.Selection([
        ('percent', 'Percentage Increase'), ('fixed', 'Fixed Increase'), ('new_amount', 'New Monthly Rent')],
        required=True, default='percent', tracking=True)
    value = fields.Float(required=True, tracking=True, digits=(16, 4))
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'Pending Approval'), ('approved', 'Approved'),
        ('applied', 'Applied'), ('rejected', 'Rejected')], default='draft', tracking=True, copy=False)
    contractual = fields.Boolean(help='Agreed in the signed lease (approved with the lease).', copy=False)
    rent_before = fields.Monetary(compute='_compute_rents')
    rent_after = fields.Monetary(compute='_compute_rents')
    reminder_sent = fields.Boolean(copy=False)
    note = fields.Char()

    def _apply(self, rate):
        self.ensure_one()
        if self.method == 'percent':
            return rate * (1 + self.value / 100.0)
        if self.method == 'fixed':
            return rate + self.value
        return self.value

    @api.depends('effective_date', 'method', 'value', 'lease_id.rent_amount')
    def _compute_rents(self):
        for rec in self:
            if not rec.lease_id or not rec.effective_date:
                rec.rent_before = rec.rent_after = 0.0
                continue
            rate = rec.lease_id.rent_amount
            for esc in rec.lease_id.escalation_ids.filtered(
                    lambda e: e.state in ('approved', 'applied') or e == rec).sorted(lambda e: (e.effective_date, e.id)):
                if esc == rec:
                    break
                if esc.effective_date <= rec.effective_date:
                    rate = esc._apply(rate)
            rec.rent_before = rate
            rec.rent_after = rec._apply(rate)

    def _compute_display_name(self):
        labels = dict(self._fields['method'].selection)
        for rec in self:
            rec.display_name = _('%(lease)s escalation %(date)s: %(method)s %(value)s',
                                 lease=rec.lease_id.name, date=rec.effective_date,
                                 method=labels.get(rec.method), value=rec.value)

    def _re_approval_amount(self):
        return (self.rent_after - self.rent_before) * 12

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('re_lease_amendment_apply'):
            return records
        for rec in records:
            if rec.lease_id.state not in ('draft',) and rec.state != 'draft':
                raise UserError(_('New escalations on submitted leases must start in draft and be approved.'))
        return records

    def write(self, vals):
        if set(vals) & {'effective_date', 'method', 'value', 'lease_id'}:
            if self.filtered(lambda e: e.state in ('approved', 'applied')):
                raise UserError(_('Approved escalations cannot be modified. Create a new escalation or amendment.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda e: e.state in ('approved', 'applied')):
            raise UserError(_('Approved escalations are part of the billing history and cannot be deleted.'))
        return super().unlink()

    def action_submit(self):
        for rec in self:
            if rec.lease_id.state == 'draft':
                raise UserError(_('Escalations on a draft lease are approved together with the lease.'))
            rec.state = 'to_approve'
            if rec._re_request_approval():
                rec._re_on_approved()

    def action_approve(self):
        self._re_approve()
        self._re_on_approved()

    def _re_on_approved(self):
        for rec in self:
            rec.state = 'approved'
            rec.lease_id._re_generate_schedule()
            rec.lease_id.message_post(body=_('Escalation approved: %s. Pending billing lines were recomputed; '
                                             'invoiced periods are unchanged.', rec.display_name))

    def _re_after_reject(self):
        self.write({'state': 'rejected'})


class ReLeaseAmendment(models.Model):
    _name = 're.lease.amendment'
    _description = 'Lease Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin']
    _order = 'id desc'
    _re_approval_document_type = 'lease_amendment'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    lease_id = fields.Many2one('re.lease', required=True, ondelete='cascade', index=True,
                               domain="[('state', 'in', ('approved', 'active', 'expiring'))]")
    company_id = fields.Many2one(related='lease_id.company_id', store=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    amendment_type = fields.Selection([
        ('rent_change', 'Rental Change'),
        ('extension', 'Term Extension'),
        ('concession', 'Rental Concession'),
        ('charge', 'Add Contractual Charge'),
        ('other', 'Other (non-financial)'),
    ], required=True, default='rent_change', tracking=True)
    effective_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    description = fields.Text(required=True)
    current_rent = fields.Monetary(compute='_compute_current_rent')
    new_rent_amount = fields.Monetary('New Monthly Rent')
    new_date_end = fields.Date('New End Date')
    concession_amount = fields.Monetary('Monthly Concession (positive amount)')
    concession_date_to = fields.Date('Concession Until')
    charge_type = fields.Selection(CHARGE_TYPES[:-1])
    charge_name = fields.Char()
    charge_amount = fields.Monetary('Charge Monthly Amount')
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'Pending Approval'), ('approved', 'Approved'),
        ('applied', 'Applied'), ('rejected', 'Rejected')], default='draft', tracking=True)

    def _compute_current_rent(self):
        for rec in self:
            rec.current_rent = rec.lease_id._get_rent_rate(rec.effective_date or fields.Date.context_today(self)) \
                if rec.lease_id else 0.0

    def _re_approval_doc_type(self):
        return 'rent_concession' if self.amendment_type == 'concession' else 'lease_amendment'

    def _re_approval_amount(self):
        if self.amendment_type == 'rent_change':
            return abs(self.new_rent_amount - self.current_rent) * 12
        if self.amendment_type == 'concession':
            return self.concession_amount
        if self.amendment_type == 'charge':
            return self.charge_amount * 12
        if self.amendment_type == 'extension':
            return self.current_rent * 12
        return 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.lease.amendment') or '/'
        return super().create(vals_list)

    def _validate(self):
        for rec in self:
            if rec.amendment_type == 'rent_change' and rec.new_rent_amount <= 0:
                raise UserError(_('Enter the new monthly rent.'))
            if rec.amendment_type == 'extension' and (not rec.new_date_end or rec.new_date_end <= rec.lease_id.date_end):
                raise UserError(_('The new end date must be after the current end date.'))
            if rec.amendment_type == 'concession' and (rec.concession_amount <= 0 or not rec.concession_date_to):
                raise UserError(_('Enter a positive monthly concession and its end date.'))
            if rec.amendment_type == 'charge' and (not rec.charge_type or rec.charge_amount <= 0):
                raise UserError(_('Enter the charge type and a positive amount.'))

    def action_submit(self):
        self._validate()
        for rec in self:
            rec.state = 'to_approve'
            if rec._re_request_approval():
                rec._re_on_approved()

    def action_approve(self):
        self._re_approve()
        self._re_on_approved()

    def _re_on_approved(self):
        self.write({'state': 'approved'})
        self._apply()

    def _re_after_reject(self):
        self.write({'state': 'rejected'})

    def _apply(self):
        for rec in self:
            lease = rec.lease_id.with_context(re_lease_amendment_apply=True)
            if rec.amendment_type == 'rent_change':
                esc = self.env['re.lease.escalation'].create({
                    'lease_id': lease.id, 'effective_date': rec.effective_date, 'method': 'new_amount',
                    'value': rec.new_rent_amount, 'note': rec.name})
                esc.write({'state': 'approved', 're_approval_state': 'approved',
                           're_approved_by_id': rec.re_approved_by_id.id or self.env.uid,
                           're_approved_date': rec.re_approved_date or fields.Datetime.now()})
            elif rec.amendment_type == 'extension':
                lease.write({'date_end': rec.new_date_end, 'alert_last_threshold': 0})
                if lease.state == 'expiring' and (rec.new_date_end - fields.Date.context_today(self)).days > \
                        lease.company_id.re_expiring_days:
                    lease.state = 'active'
            elif rec.amendment_type == 'concession':
                self.env['re.lease.charge'].with_context(re_lease_amendment_apply=True).create({
                    'lease_id': lease.id, 'charge_type': 'concession', 'name': _('Concession %s', rec.name),
                    'amount': -rec.concession_amount, 'date_from': rec.effective_date,
                    'date_to': rec.concession_date_to})
            elif rec.amendment_type == 'charge':
                self.env['re.lease.charge'].with_context(re_lease_amendment_apply=True).create({
                    'lease_id': lease.id, 'charge_type': rec.charge_type,
                    'name': rec.charge_name or dict(CHARGE_TYPES)[rec.charge_type],
                    'amount': rec.charge_amount, 'date_from': rec.effective_date})
            lease._re_generate_schedule()
            rec.state = 'applied'
            lease.message_post(body=_('Amendment %(name)s applied: %(desc)s', name=rec.name, desc=rec.description))
