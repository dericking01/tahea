# -*- coding: utf-8 -*-
"""Investment appraisal.

All figures are PROJECTIONS based on the assumptions recorded on the record.

Definitions (year y = 1..N, N = holding period):
  GPR_y      = annual gross potential rent x (1 + rent growth)^(y-1)
  EGI_y      = GPR_y x expected occupancy
  OPEX_y     = (annual opex + annual maintenance) x (1 + opex growth)^(y-1)
  NOI_y      = EGI_y - OPEX_y           (excludes financing, tax, depreciation, capex)
  CF_y       = NOI_y - capex reserve_y  (+ net sale proceeds in year N)
  Net sale   = NOI_(N+1) / exit cap rate x (1 - selling costs %)
  CF_0       = - total investment (price + land + construction + fees + other)
  NPV        = sum CF_y / (1 + discount rate)^y, y = 0..N
  IRR        = rate where NPV = 0 (bisection)
  Payback    = years until cumulative CF (excluding sale proceeds) turns positive
  ROI        = (sum CF_1..N incl. sale - investment) / investment
  Gross yield= GPR_1 / total investment;  Net yield = NOI_1 / total investment
  Break-even occupancy = (OPEX_1 + annual debt service) / GPR_1
  Debt service = level annuity on the loan amount (interest rate, term)
  Equity IRR uses CF_y - debt service, CF_0 = - equity, and repays the
  outstanding loan balance from the sale proceeds.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

ASSUMPTION_FIELDS = {
    'purchase_price', 'land_cost', 'construction_cost', 'professional_fees', 'other_costs', 'loan_amount',
    'interest_rate', 'loan_term_years', 'annual_gross_rent', 'expected_occupancy', 'annual_opex',
    'annual_maintenance', 'annual_capex', 'rent_growth', 'opex_growth', 'discount_rate', 'holding_years',
    'exit_cap_rate', 'selling_costs_pct',
}


def _npv(rate, flows):
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(flows))


def _irr(flows):
    if not flows or all(f >= 0 for f in flows) or all(f <= 0 for f in flows):
        return None
    lo, hi = -0.99, 10.0
    f_lo, f_hi = _npv(lo, flows), _npv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _i in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, flows)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


class ReInvestment(models.Model):
    _name = 're.investment'
    _description = 'Investment Opportunity / Appraisal'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin']
    _order = 'id desc'
    _re_approval_document_type = 'investment'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(copy=False, readonly=True, default='/')
    version = fields.Integer(default=1, readonly=True)
    original_id = fields.Many2one('re.investment', 'Original Case', readonly=True, copy=False)
    parent_id = fields.Many2one('re.investment', 'Revision Of', readonly=True, copy=False)
    revision_reason = fields.Text(copy=False)
    is_scenario = fields.Boolean(readonly=True, copy=False)
    scenario_of_id = fields.Many2one('re.investment', readonly=True, copy=False)
    scenario_name = fields.Char()
    state = fields.Selection([
        ('draft', 'Draft'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected'),
        ('acquired', 'Acquired / Operational'), ('superseded', 'Superseded by Revision')],
        default='draft', tracking=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    manager_id = fields.Many2one('res.users', 'Investment Manager', default=lambda self: self.env.user, tracking=True)
    property_type_id = fields.Many2one('re.property.type', 'Investment Category')
    location = fields.Char()
    region = fields.Char()
    funding_source = fields.Selection([('equity', 'Equity'), ('debt', 'Debt'), ('mixed', 'Equity and Debt'),
                                       ('fund', 'Investment Fund'), ('jv', 'Joint Venture')], default='mixed')
    property_id = fields.Many2one('re.property', 'Resulting Property', tracking=True,
                                  help='Link once the property is acquired / operational for actual vs projected.')

    # ---- Assumptions --------------------------------------------------------------------
    purchase_price = fields.Monetary(tracking=True)
    land_cost = fields.Monetary('Land Acquisition Costs', tracking=True)
    construction_cost = fields.Monetary(tracking=True)
    professional_fees = fields.Monetary(tracking=True)
    other_costs = fields.Monetary('Other Costs (stamp duty, legal...)', tracking=True)
    total_investment = fields.Monetary(compute='_compute_metrics', store=True)
    loan_amount = fields.Monetary(tracking=True)
    interest_rate = fields.Float('Loan Interest Rate (%)', tracking=True)
    loan_term_years = fields.Integer('Loan Term (years)', default=10)
    annual_gross_rent = fields.Monetary('Gross Potential Rent (annual, 100% let)', tracking=True)
    expected_occupancy = fields.Float('Expected Occupancy (%)', default=90.0, tracking=True)
    annual_opex = fields.Monetary('Operating Expenses (annual)', tracking=True)
    annual_maintenance = fields.Monetary('Maintenance (annual)', tracking=True)
    annual_capex = fields.Monetary('Capex Reserve (annual)', tracking=True)
    rent_growth = fields.Float('Rent Growth (%/yr)', default=5.0, tracking=True)
    opex_growth = fields.Float('Opex Growth (%/yr)', default=5.0, tracking=True)
    discount_rate = fields.Float('Discount Rate (%)', default=15.0, tracking=True)
    holding_years = fields.Integer('Investment Period (years)', default=10, tracking=True)
    exit_cap_rate = fields.Float('Exit Capitalisation Rate (%)', default=10.0, tracking=True)
    selling_costs_pct = fields.Float('Selling Costs (%)', default=3.0)
    assumptions_note = fields.Html('Assumption Sources & Rationale')

    # ---- Results ------------------------------------------------------------------------
    cashflow_ids = fields.One2many('re.investment.cashflow', 'investment_id', readonly=True)
    noi_year1 = fields.Monetary('Projected NOI (Year 1)', compute='_compute_metrics', store=True)
    gross_yield = fields.Float('Gross Yield (%)', compute='_compute_metrics', store=True)
    net_yield = fields.Float('Net Yield (%)', compute='_compute_metrics', store=True)
    npv = fields.Monetary('NPV', compute='_compute_metrics', store=True)
    irr = fields.Float('Project IRR (%)', compute='_compute_metrics', store=True)
    equity_irr = fields.Float('Equity IRR (%)', compute='_compute_metrics', store=True)
    roi = fields.Float('ROI over Period (%)', compute='_compute_metrics', store=True)
    payback_years = fields.Float('Payback (years)', compute='_compute_metrics', store=True)
    payback_note = fields.Char(compute='_compute_metrics', store=True)
    annual_debt_service = fields.Monetary(compute='_compute_metrics', store=True)
    dscr_year1 = fields.Float('DSCR (Year 1)', compute='_compute_metrics', store=True)
    break_even_occupancy = fields.Float('Break-even Occupancy (%)', compute='_compute_metrics', store=True)

    # ---- Actual vs projected -------------------------------------------------------------
    compare_year = fields.Integer('Comparison Year', default=lambda self: fields.Date.today().year)
    actual_revenue = fields.Monetary(compute='_compute_actuals')
    actual_opex = fields.Monetary(compute='_compute_actuals')
    actual_maintenance = fields.Monetary(compute='_compute_actuals')
    actual_noi = fields.Monetary(compute='_compute_actuals')
    actual_occupancy = fields.Float(compute='_compute_actuals')
    actual_investment = fields.Monetary(compute='_compute_actuals')
    projected_revenue = fields.Monetary(compute='_compute_actuals')
    projected_opex = fields.Monetary(compute='_compute_actuals')
    projected_maintenance = fields.Monetary(compute='_compute_actuals')
    projected_noi = fields.Monetary(compute='_compute_actuals')
    variance_explanation = fields.Text(compute='_compute_actuals')
    materiality_pct = fields.Float('Materiality Threshold (%)', default=10.0)

    @api.constrains('expected_occupancy', 'holding_years', 'exit_cap_rate', 'discount_rate')
    def _check_assumptions(self):
        for rec in self:
            if not 0 <= rec.expected_occupancy <= 100:
                raise ValidationError(_('Occupancy must be between 0 and 100%.'))
            if rec.holding_years <= 0 or rec.holding_years > 50:
                raise ValidationError(_('The investment period must be between 1 and 50 years.'))
            if rec.exit_cap_rate <= 0:
                raise ValidationError(_('The exit cap rate must be positive.'))
            if rec.discount_rate <= -100:
                raise ValidationError(_('Invalid discount rate.'))

    def _projection(self):
        """Returns (rows, metrics) for the current assumptions."""
        self.ensure_one()
        total = self.purchase_price + self.land_cost + self.construction_cost + self.professional_fees + self.other_costs
        occ = self.expected_occupancy / 100.0
        g_r, g_o = self.rent_growth / 100.0, self.opex_growth / 100.0
        n = self.holding_years
        r = self.interest_rate / 100.0
        debt_service = 0.0
        if self.loan_amount and self.loan_term_years:
            debt_service = self.loan_amount / self.loan_term_years if not r else \
                self.loan_amount * r / (1 - (1 + r) ** (-self.loan_term_years))
        rows = []
        flows = [-total]
        eq_flows = [-(total - self.loan_amount)]
        balance = self.loan_amount
        cumulative = -total
        payback = None
        for y in range(1, n + 2):
            gpr = self.annual_gross_rent * (1 + g_r) ** (y - 1)
            egi = gpr * occ
            opex = (self.annual_opex + self.annual_maintenance) * (1 + g_o) ** (y - 1)
            noi = egi - opex
            if y == n + 1:
                break
            capex = self.annual_capex
            ds = debt_service if y <= self.loan_term_years else 0.0
            interest = balance * r
            balance = max(0.0, balance - (ds - interest)) if ds else balance
            cf = noi - capex
            prev_cum = cumulative
            cumulative += cf
            if payback is None and cumulative >= 0 > prev_cum:
                payback = (y - 1) + (-prev_cum / cf if cf else 0)
            rows.append({'year': y, 'gpr': gpr, 'vacancy': gpr - egi, 'egi': egi, 'opex': opex, 'noi': noi,
                         'capex': capex, 'debt_service': ds, 'sale_proceeds': 0.0, 'net_cf': cf})
            flows.append(cf)
            eq_flows.append(cf - ds)
        # sale at end of year n based on forward NOI (year n+1)
        sale = noi / (self.exit_cap_rate / 100.0) * (1 - self.selling_costs_pct / 100.0) if n else 0.0
        if rows:
            rows[-1]['sale_proceeds'] = sale
            rows[-1]['net_cf'] += sale
            flows[-1] += sale
            eq_flows[-1] += sale - balance
        disc = self.discount_rate / 100.0
        cum = flows[0]
        for i, row in enumerate(rows, start=1):
            row['discounted_cf'] = flows[i] / (1 + disc) ** i
            cum += flows[i]
            row['cumulative_cf'] = cum
        npv = _npv(disc, flows)
        irr = _irr(flows)
        eirr = _irr(eq_flows) if self.loan_amount else irr
        gpr1 = self.annual_gross_rent
        noi1 = rows[0]['noi'] if rows else 0.0
        metrics = {
            'total_investment': total,
            'noi_year1': noi1,
            'gross_yield': 100.0 * gpr1 / total if total else 0.0,
            'net_yield': 100.0 * noi1 / total if total else 0.0,
            'npv': npv,
            'irr': 100.0 * irr if irr is not None else 0.0,
            'equity_irr': 100.0 * eirr if eirr is not None else 0.0,
            'roi': 100.0 * (sum(flows[1:]) - total) / total if total else 0.0,
            'payback_years': payback or 0.0,
            'payback_note': _('Not reached within the investment period (excluding sale)') if payback is None else '',
            'annual_debt_service': debt_service,
            'dscr_year1': noi1 / debt_service if debt_service else 0.0,
            'break_even_occupancy': 100.0 * ((rows[0]['opex'] if rows else 0.0) + debt_service) / gpr1 if gpr1 else 0.0,
        }
        return rows, metrics

    @api.depends(*ASSUMPTION_FIELDS)
    def _compute_metrics(self):
        for rec in self:
            _rows, metrics = rec._projection()
            rec.update(metrics)

    def action_compute_cashflows(self):
        for rec in self:
            rows, _metrics = rec._projection()
            rec.cashflow_ids.unlink()
            self.env['re.investment.cashflow'].create([dict(row, investment_id=rec.id) for row in rows])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', '/') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('re.investment') or '/'
        records = super().create(vals_list)
        records.action_compute_cashflows()
        return records

    def write(self, vals):
        if ASSUMPTION_FIELDS & set(vals):
            locked = self.filtered(lambda r: r.state not in ('draft', 'rejected'))
            if locked:
                raise UserError(_('Assumptions of %s are locked (%s). Create an authorised revision or a scenario '
                                  'instead.', locked[0].display_name,
                                  dict(self._fields['state'].selection)[locked[0].state]))
        res = super().write(vals)
        if ASSUMPTION_FIELDS & set(vals):
            self.action_compute_cashflows()
        return res

    def _compute_display_name(self):
        for rec in self:
            label = '%s %s v%s' % (rec.code or '', rec.name, rec.version)
            if rec.is_scenario:
                label += ' [%s]' % (rec.scenario_name or _('Scenario'))
            rec.display_name = label

    def _re_approval_amount(self):
        return self.total_investment

    def action_submit(self):
        for rec in self:
            if rec.is_scenario:
                raise UserError(_('Scenarios are simulations and cannot be submitted. Promote the assumptions to a '
                                  'revision instead.'))
            if not rec.total_investment:
                raise UserError(_('Enter the investment costs.'))
            rec.state = 'under_review'
            if rec._re_request_approval():
                rec._re_on_approved()

    def action_approve(self):
        self._re_approve()
        self._re_on_approved()

    def _re_on_approved(self):
        for rec in self:
            rec.action_compute_cashflows()
            if rec.parent_id:
                previous = self.search([('original_id', '=', rec.original_id.id), ('state', '=', 'approved'),
                                        ('id', '!=', rec.id)]) | rec.original_id.filtered(lambda o: o.state == 'approved')
                previous.write({'state': 'superseded'})
            rec.state = 'approved'

    def _re_after_reject(self):
        self.write({'state': 'rejected'})

    def action_create_revision(self):
        self.ensure_one()
        if self.state not in ('approved', 'acquired'):
            raise UserError(_('Only approved cases are revised; edit drafts directly.'))
        original = self.original_id or self
        last = self.search([('original_id', '=', original.id)], order='version desc', limit=1)
        rev = self.copy({'name': self.name, 'parent_id': self.id, 'original_id': original.id,
                         'version': max(last.version, self.version) + 1, 'state': 'draft',
                         'property_id': self.property_id.id})
        rev.message_post(body=_('Revision of %s. The approved case remains unchanged for historical comparison.',
                                self.display_name))
        return {'type': 'ir.actions.act_window', 'res_model': 're.investment', 'res_id': rev.id, 'view_mode': 'form'}

    def action_create_scenario(self):
        self.ensure_one()
        sc = self.copy({'is_scenario': True, 'scenario_of_id': self.id, 'scenario_name': _('Scenario'),
                        'state': 'draft', 'original_id': (self.original_id or self).id, 'version': self.version})
        return {'type': 'ir.actions.act_window', 'res_model': 're.investment', 'res_id': sc.id, 'view_mode': 'form'}

    def action_mark_acquired(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved investments can be marked as acquired.'))
            if not rec.property_id:
                raise UserError(_('Link the resulting property first.'))
        self.write({'state': 'acquired'})

    def action_view_scenarios(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 're.investment', 'view_mode': 'list,form',
                'name': _('Versions & Scenarios'),
                'domain': ['|', '|', ('id', '=', (self.original_id or self).id),
                           ('original_id', '=', (self.original_id or self).id), ('scenario_of_id', '=', self.id)]}

    def _compute_actuals(self):
        Analytics = self.env['re.analytics']
        for rec in self:
            vals = dict.fromkeys(['actual_revenue', 'actual_opex', 'actual_maintenance', 'actual_noi',
                                  'actual_occupancy', 'actual_investment', 'projected_revenue', 'projected_opex',
                                  'projected_maintenance', 'projected_noi'], 0.0)
            vals['variance_explanation'] = False
            prop = rec.property_id
            if prop and rec.compare_year:
                d1 = fields.Date.from_string('%s-01-01' % rec.compare_year)
                d2 = fields.Date.from_string('%s-12-31' % rec.compare_year)
                fin = Analytics._financials(prop.ids, d1, d2)
                vals.update({'actual_revenue': fin['revenue'], 'actual_opex': fin['opex'],
                             'actual_maintenance': fin['maintenance'], 'actual_noi': fin['noi'],
                             'actual_occupancy': prop.occupancy_rate,
                             'actual_investment': prop.purchase_price + prop.acquisition_costs + Analytics._capex(
                                 prop.ids, None, d2)})
                start_year = (prop.acquisition_date or prop.create_date.date()).year
                idx = rec.compare_year - start_year + 1
                row = rec.cashflow_ids.filtered(lambda c: c.year == idx)[:1]
                if row:
                    maint_share = rec.annual_maintenance / (rec.annual_opex + rec.annual_maintenance) \
                        if (rec.annual_opex + rec.annual_maintenance) else 0.0
                    vals.update({'projected_revenue': row.egi, 'projected_opex': row.opex,
                                 'projected_maintenance': row.opex * maint_share, 'projected_noi': row.noi})
                lines = []
                pairs = [(_('Rental revenue'), vals['actual_revenue'], vals['projected_revenue']),
                         (_('Operating expenses'), vals['actual_opex'], vals['projected_opex']),
                         (_('Maintenance'), vals['actual_maintenance'], vals['projected_maintenance']),
                         (_('NOI'), vals['actual_noi'], vals['projected_noi']),
                         (_('Occupancy %'), vals['actual_occupancy'], rec.expected_occupancy),
                         (_('Investment cost'), vals['actual_investment'], rec.total_investment)]
                for label, actual, projected in pairs:
                    if projected and abs(actual - projected) / abs(projected) * 100 >= rec.materiality_pct:
                        lines.append(_('%(l)s: actual %(a)s vs projected %(p)s (%(v)+.1f%%) - material variance, '
                                       'investigate.', l=label, a=round(actual, 2), p=round(projected, 2),
                                       v=100 * (actual - projected) / abs(projected)))
                if not row:
                    lines.append(_('Year %s is outside the projection horizon.', rec.compare_year))
                vals['variance_explanation'] = '\n'.join(lines) or _('No material variances.')
            rec.update(vals)


class ReInvestmentCashflow(models.Model):
    _name = 're.investment.cashflow'
    _description = 'Projected Investment Cash Flow'
    _order = 'investment_id, year'

    investment_id = fields.Many2one('re.investment', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='investment_id.currency_id')
    year = fields.Integer(required=True)
    gpr = fields.Monetary('Gross Potential Rent')
    vacancy = fields.Monetary('Vacancy Loss')
    egi = fields.Monetary('Effective Gross Income')
    opex = fields.Monetary('Operating Expenses')
    noi = fields.Monetary('NOI')
    capex = fields.Monetary('Capex Reserve')
    debt_service = fields.Monetary()
    sale_proceeds = fields.Monetary('Net Sale Proceeds')
    net_cf = fields.Monetary('Net Cash Flow (unlevered)')
    discounted_cf = fields.Monetary('Discounted CF')
    cumulative_cf = fields.Monetary('Cumulative CF')
