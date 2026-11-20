# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ReServiceChargeBudget(models.Model):
    """Annual (or other period) service-charge budget for a building or property.

    1. Budget lines per cost category, each mapped to the expense accounts whose
       postings represent actual service-charge expenditure.
    2. Allocation across rentable units by area, equal share or custom %. Vacant
       units' shares are a landlord cost (void cost) - never re-spread to tenants.
    3. After approval, monthly charges are added to the leases (billing engine).
    4. Year-end reconciliation: actual cost x share - amount billed = balancing
       charge (invoice) or refund (credit note), created as drafts for review."""
    _name = 're.service.charge.budget'
    _description = 'Service-Charge Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin']
    _order = 'date_from desc, id desc'
    _re_approval_document_type = 'service_charge_budget'

    name = fields.Char(required=True, tracking=True)
    property_id = fields.Many2one('re.property', required=True, index=True, tracking=True)
    building_id = fields.Many2one('re.building', domain="[('property_id', '=', property_id)]", tracking=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    manager_id = fields.Many2one(related='property_id.manager_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)
    months = fields.Float(compute='_compute_months', store=True)
    allocation_basis = fields.Selection([
        ('area', 'By Lettable Area'), ('equal', 'Equal Share per Unit'), ('custom', 'Custom % per Unit')],
        required=True, default='area', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'Pending Approval'), ('approved', 'Approved'),
        ('applied', 'Billing to Tenants'), ('reconciled', 'Reconciled'), ('closed', 'Closed'),
        ('rejected', 'Rejected')], default='draft', tracking=True)
    line_ids = fields.One2many('re.service.charge.budget.line', 'budget_id', copy=True)
    allocation_ids = fields.One2many('re.service.charge.allocation', 'budget_id')
    total_budget = fields.Monetary(compute='_compute_totals', store=True, tracking=True)
    total_actual = fields.Monetary(compute='_compute_actuals')
    variance = fields.Monetary('Variance (Actual - Budget)', compute='_compute_actuals')
    variance_pct = fields.Float(compute='_compute_actuals')
    total_billed = fields.Monetary(compute='_compute_actuals')
    total_collected = fields.Monetary(compute='_compute_actuals')
    landlord_void_share = fields.Monetary('Vacant-unit (Landlord) Share', compute='_compute_actuals')
    recon_move_ids = fields.Many2many('account.move', string='Reconciliation Documents', readonly=True, copy=False)
    note = fields.Text()

    @api.depends('date_from', 'date_to')
    def _compute_months(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                d = relativedelta(rec.date_to + timedelta(days=1), rec.date_from)
                rec.months = d.years * 12 + d.months + d.days / 30.0
            else:
                rec.months = 0.0

    @api.depends('line_ids.budget_amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_budget = sum(rec.line_ids.mapped('budget_amount'))

    def _compute_actuals(self):
        for rec in self:
            rec.total_actual = sum(rec.line_ids.mapped('actual_amount'))
            rec.variance = rec.total_actual - rec.total_budget
            rec.variance_pct = 100.0 * rec.variance / rec.total_budget if rec.total_budget else 0.0
            rec.total_billed = sum(rec.allocation_ids.mapped('billed_amount'))
            rec.total_collected = sum(rec.allocation_ids.mapped('collected_amount'))
            rec.landlord_void_share = sum(rec.allocation_ids.filtered(lambda a: not a.lease_id).mapped('actual_share'))

    @api.constrains('date_from', 'date_to', 'property_id', 'building_id', 'state')
    def _check_dates(self):
        for rec in self:
            if rec.date_to <= rec.date_from:
                raise ValidationError(_('The budget end must be after its start.'))
            overlap = self.search([
                ('id', '!=', rec.id), ('property_id', '=', rec.property_id.id),
                ('building_id', '=', rec.building_id.id), ('state', 'not in', ('rejected', 'draft')),
                ('date_from', '<=', rec.date_to), ('date_to', '>=', rec.date_from)], limit=1)
            if overlap and rec.state not in ('rejected', 'draft'):
                raise ValidationError(_('Budget %s already covers this period for the same building.', overlap.name))

    def _re_approval_amount(self):
        return self.total_budget

    def _scope_units(self):
        self.ensure_one()
        domain = [('property_id', '=', self.property_id.id), ('is_lettable', '=', True),
                  ('service_charge_basis', '!=', 'excluded')]
        if self.building_id:
            domain.append(('building_id', '=', self.building_id.id))
        return self.env['re.unit'].search(domain)

    def _lease_for_unit(self, unit):
        return self.env['re.lease'].search([
            ('unit_ids', 'in', unit.id), ('state', 'in', ('active', 'expiring', 'approved')),
            ('date_start', '<=', self.date_to), ('effective_end_date', '>=', self.date_from)],
            order='date_start desc', limit=1)

    def action_compute_allocation(self):
        for rec in self:
            if rec.state not in ('draft', 'approved', 'applied'):
                raise UserError(_('Allocation can only be recomputed before reconciliation.'))
            units = rec._scope_units()
            if not units:
                raise UserError(_('No rentable units in scope.'))
            total_area = sum(units.mapped('area_sqm'))
            vals = []
            for unit in units:
                if rec.allocation_basis == 'area':
                    if not total_area:
                        raise UserError(_('Units have no area; use another allocation basis.'))
                    share = 100.0 * unit.area_sqm / total_area
                elif rec.allocation_basis == 'equal':
                    share = 100.0 / len(units)
                else:
                    share = unit.service_charge_share
                existing = rec.allocation_ids.filtered(lambda a: a.unit_id == unit)
                lease = rec._lease_for_unit(unit)
                if existing:
                    existing.write({'share_pct': share, 'lease_id': existing.lease_id.id or lease.id})
                else:
                    vals.append({'budget_id': rec.id, 'unit_id': unit.id, 'share_pct': share, 'lease_id': lease.id})
            self.env['re.service.charge.allocation'].create(vals)
            if rec.allocation_basis == 'custom':
                total = sum(rec.allocation_ids.mapped('share_pct'))
                if abs(total - 100.0) > 0.01:
                    raise UserError(_('Custom service-charge shares add up to %.2f%% instead of 100%%.', total))

    def action_submit(self):
        for rec in self:
            if not rec.line_ids or not rec.total_budget:
                raise UserError(_('Add budget lines first.'))
            if not rec.allocation_ids:
                rec.action_compute_allocation()
            rec.state = 'to_approve'
            if rec._re_request_approval():
                rec.state = 'approved'

    def action_approve(self):
        self._re_approve()
        self.write({'state': 'approved'})

    def _re_after_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'to_approve'):
                raise UserError(_('Only rejected or pending budgets can be reset.'))
        self.write({'state': 'draft', 're_approval_state': 'none'})

    def action_apply_to_leases(self):
        """Add the monthly service charge to every lease in scope (idempotent)."""
        Charge = self.env['re.lease.charge'].with_context(re_lease_amendment_apply=True)
        for rec in self:
            if rec.state not in ('approved', 'applied'):
                raise UserError(_('The budget must be approved before billing tenants.'))
            for alloc in rec.allocation_ids:
                lease = alloc.lease_id or rec._lease_for_unit(alloc.unit_id)
                if not lease or not lease.service_charge_applicable:
                    continue
                alloc.lease_id = lease
                existing = lease.charge_ids.filtered(lambda c: c.service_charge_allocation_id == alloc)
                if existing:
                    continue
                Charge.create({
                    'lease_id': lease.id, 'charge_type': 'service_charge',
                    'name': _('Service charge %(budget)s - %(unit)s', budget=rec.name, unit=alloc.unit_id.name),
                    'amount': rec.currency_id.round(alloc.monthly_charge),
                    'date_from': max(rec.date_from, lease.date_start),
                    'date_to': min(rec.date_to, lease.date_end),
                    'service_charge_budget_id': rec.id,
                    'service_charge_allocation_id': alloc.id,
                })
                lease._re_generate_schedule()
                lease.message_post(body=_('Service charge from approved budget %s added.', rec.name))
            rec.state = 'applied'

    def action_reconcile(self):
        """Year-end reconciliation: creates DRAFT balancing invoices / credit notes."""
        self.env.flush_all()
        self.env.invalidate_all()  # actual/billed figures must reflect the latest postings
        for rec in self:
            if rec.state != 'applied':
                raise UserError(_('Only budgets billed to tenants can be reconciled.'))
            moves = self.env['account.move']
            product = rec.company_id._re_get_product('service_charge_recon')
            journal = rec.company_id.re_rental_journal_id or self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', rec.company_id.id)], limit=1)
            for alloc in rec.allocation_ids.filtered('lease_id'):
                balance = rec.currency_id.round(alloc.balance)
                if rec.currency_id.is_zero(balance) or alloc.recon_move_id:
                    continue
                move = self.env['account.move'].with_company(rec.company_id).create({
                    'move_type': 'out_invoice' if balance > 0 else 'out_refund',
                    'partner_id': alloc.lease_id.tenant_id.id,
                    'invoice_date': fields.Date.context_today(self),
                    'journal_id': journal.id,
                    'currency_id': rec.currency_id.id,
                    're_lease_id': alloc.lease_id.id,
                    'invoice_origin': rec.name,
                    'ref': _('Service-charge reconciliation %(b)s (%(f)s - %(t)s)', b=rec.name, f=rec.date_from,
                             t=rec.date_to),
                    'invoice_line_ids': [(0, 0, {
                        'product_id': product.id, 'quantity': 1, 'price_unit': abs(balance),
                        'name': _('Service-charge reconciliation %(unit)s: actual share %(act)s - billed %(bill)s',
                                  unit=alloc.unit_id.name, act=rec.currency_id.format(alloc.actual_share),
                                  bill=rec.currency_id.format(alloc.billed_amount)),
                        'analytic_distribution': rec.property_id._re_analytic_distribution(rec.building_id),
                        're_charge_type': 'service_charge_recon',
                        're_service_charge_budget_id': rec.id,
                        're_period_start': rec.date_from, 're_period_end': rec.date_to})],
                })
                alloc.recon_move_id = move
                moves |= move
            rec.write({'state': 'reconciled', 'recon_move_ids': [(4, m.id) for m in moves]})
            rec.message_post(body=_('%s reconciliation documents created in draft for accountant review.', len(moves)))

    def action_close(self):
        self.write({'state': 'closed'})

    def action_view_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Actual Service-Charge Expenditure'),
            'res_model': 'account.move.line', 'view_mode': 'list,pivot',
            'domain': self._actual_domain(self.line_ids.mapped('account_ids').ids),
        }

    def _actual_domain(self, account_ids):
        self.ensure_one()
        domain = [('parent_state', '=', 'posted'), ('account_id', 'in', account_ids),
                  ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.building_id:
            domain.append(('re_building_id', '=', self.building_id.id))
        else:
            domain.append(('re_property_id', '=', self.property_id.id))
        return domain

    def action_print_reconciliation(self):
        return self.env.ref('real_estate_lifecycle.action_report_service_charge').report_action(self)


class ReServiceChargeBudgetLine(models.Model):
    _name = 're.service.charge.budget.line'
    _description = 'Service-Charge Budget Line'

    budget_id = fields.Many2one('re.service.charge.budget', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='budget_id.currency_id')
    company_id = fields.Many2one(related='budget_id.company_id')
    name = fields.Char('Cost Category', required=True)
    account_ids = fields.Many2many('account.account', string='Expense Accounts',
                                   help='Posted expenditure on these accounts, allocated to the building/property '
                                        '(analytic), is the actual cost of this category.')
    budget_amount = fields.Monetary(required=True)
    actual_amount = fields.Monetary(compute='_compute_actual')
    variance = fields.Monetary(compute='_compute_actual')

    def _compute_actual(self):
        AML = self.env['account.move.line'].sudo()
        for rec in self:
            if not rec.account_ids or not rec.budget_id.date_from:
                rec.actual_amount = 0.0
            else:
                lines = AML.search(rec.budget_id._actual_domain(rec.account_ids.ids))
                rec.actual_amount = sum(lines.mapped('balance'))
            rec.variance = rec.actual_amount - rec.budget_amount


class ReServiceChargeAllocation(models.Model):
    _name = 're.service.charge.allocation'
    _description = 'Service-Charge Allocation'
    _order = 'budget_id, unit_id'

    budget_id = fields.Many2one('re.service.charge.budget', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    unit_id = fields.Many2one('re.unit', required=True)
    lease_id = fields.Many2one('re.lease')
    tenant_id = fields.Many2one(related='lease_id.tenant_id')
    share_pct = fields.Float('Share (%)')
    budget_share = fields.Monetary(compute='_compute_amounts')
    monthly_charge = fields.Monetary(compute='_compute_amounts')
    billed_amount = fields.Monetary(compute='_compute_billing')
    collected_amount = fields.Monetary(compute='_compute_billing')
    actual_share = fields.Monetary(compute='_compute_amounts')
    balance = fields.Monetary('Balancing Charge (+) / Refund (-)', compute='_compute_billing')
    recon_move_id = fields.Many2one('account.move', readonly=True)

    @api.depends('share_pct', 'budget_id.total_budget', 'budget_id.months')
    def _compute_amounts(self):
        for rec in self:
            budget = rec.budget_id
            rec.budget_share = budget.total_budget * rec.share_pct / 100.0
            rec.monthly_charge = rec.budget_share / budget.months if budget.months else 0.0
            rec.actual_share = budget.total_actual * rec.share_pct / 100.0

    def _compute_billing(self):
        AML = self.env['account.move.line'].sudo()
        for rec in self:
            billed = collected = 0.0
            if rec.lease_id:
                lines = AML.search([('re_schedule_line_id.charge_id.service_charge_allocation_id', '=', rec.id),
                                    ('re_charge_type', '=', 'service_charge'),
                                    ('parent_state', '=', 'posted'), ('display_type', '=', 'product')])
                for line in lines:
                    sign = -1 if line.move_id.move_type == 'out_refund' else 1
                    amount = sign * abs(line.balance)
                    billed += amount
                    move = line.move_id
                    paid_ratio = (1 - move.amount_residual / move.amount_total) if move.amount_total else 0.0
                    collected += amount * paid_ratio
            rec.billed_amount = billed
            rec.collected_amount = collected
            rec.balance = rec.actual_share - billed if rec.lease_id else 0.0
