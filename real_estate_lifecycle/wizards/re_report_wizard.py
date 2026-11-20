# -*- coding: utf-8 -*-
"""Management report engine.

Every report is produced from live records as a list of tables
({title, columns, rows, totals}) plus the reporting period and the calculation
definitions. The same dataset renders to PDF (QWeb) and Excel (xlsxwriter).
Property selection is searched as the current user, so record rules and company
restrictions apply to every report."""
import base64
import io
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.re_dashboard import KPI_DEFINITIONS, RENTAL_TYPES

REPORT_TYPES = [
    ('property_register', 'Property Register'),
    ('ownership', 'Property Ownership & Valuation'),
    ('occupancy', 'Unit Register / Occupancy & Vacancy'),
    ('rent_roll', 'Rent Roll'),
    ('lease_expiry', 'Lease Expiry & Renewal'),
    ('escalation', 'Rental Escalation Report'),
    ('rate_comparison', 'Rental Rate Comparison (contract vs market)'),
    ('rental_income', 'Rental Income by Charge Type'),
    ('tenant_ageing', 'Tenant Ageing'),
    ('collection', 'Collection Efficiency'),
    ('property_income', 'Property Income Statement (NOI)'),
    ('property_comparison', 'Property Performance Comparison'),
    ('deposit_liability', 'Security Deposit Liability'),
    ('service_charge', 'Service-Charge Budget vs Actual'),
    ('work_orders', 'Work-Order Register & Maintenance Expenditure'),
    ('pm_compliance', 'Preventive Maintenance Compliance'),
    ('asset_replacement', 'Equipment Condition & Replacement Analysis'),
    ('contractor', 'Contractor Performance'),
    ('investment', 'Investment Appraisal Comparison'),
]


class ReReportWizard(models.TransientModel):
    _name = 're.report.wizard'
    _description = 'Real Estate Management Report'

    report_type = fields.Selection(REPORT_TYPES, required=True, default='rent_roll')
    date_from = fields.Date(default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(default=fields.Date.context_today)
    property_ids = fields.Many2many('re.property', string='Properties (empty = all authorised)')
    portfolio_id = fields.Many2one('re.portfolio')
    only_vacant = fields.Boolean('Vacant units only')
    expiry_days = fields.Integer('Lease expiry window (days)', default=180)

    # ------------------------------------------------------------------
    def _properties(self):
        domain = [('state', '!=', 'disposed')]
        if self.property_ids:
            domain.append(('id', 'in', self.property_ids.ids))
        if self.portfolio_id:
            domain.append(('portfolio_id', '=', self.portfolio_id.id))
        return self.env['re.property'].search(domain)  # as user: record rules apply

    def _re_cell(self, value):
        """(text, is_numeric) for report rendering."""
        if isinstance(value, bool) or value is None:
            return ('' if value is None else (_('Yes') if value else _('No')), False)
        if isinstance(value, (int, float)):
            return ('{:,.2f}'.format(value) if isinstance(value, float) else '{:,}'.format(value), True)
        return (value, False)

    def _fmt_date(self, d):
        return fields.Date.to_string(d) if d else ''

    def _get_report_data(self):
        self.ensure_one()
        props = self._properties()
        method = getattr(self, '_data_%s' % self.report_type)
        tables, definitions = method(props)
        return {
            'title': dict(REPORT_TYPES)[self.report_type],
            'company': self.env.company.name,
            'currency': self.env.company.currency_id.name,
            'date_from': self._fmt_date(self.date_from), 'date_to': self._fmt_date(self.date_to),
            'generated': fields.Datetime.to_string(fields.Datetime.now()),
            'user': self.env.user.name,
            'scope': ', '.join(props.mapped('code')) if len(props) <= 15 else _('%s properties', len(props)),
            'tables': tables,
            'definitions': definitions,
        }

    def _mk_table(self, title, columns, rows, totals=None):
        return {'title': title, 'columns': columns, 'rows': rows, 'totals': totals}

    @staticmethod
    def _sum(rows, idx):
        return sum(r[idx] or 0.0 for r in rows if isinstance(r[idx], (int, float)))

    # ------------------------------------------------------------------ data builders
    def _data_property_register(self, props):
        rows = [[p.code, p.name, p.property_type_id.name, p.region or '', p.district or '', p.legal_owner_id.name or '',
                 p.manager_id.name or '', p.building_count, p.unit_count, round(p.lettable_area_sqm, 2),
                 round(p.occupancy_rate, 1), p.current_valuation, p.title_number or '',
                 dict(p._fields['state'].selection)[p.state]] for p in props.sudo()]
        cols = ['Code', 'Property', 'Type', 'Region', 'District', 'Legal Owner', 'Manager', 'Buildings', 'Units',
                'Lettable m²', 'Occupancy %', 'Value', 'Title No.', 'Status']
        return [self._mk_table(_('Properties'), cols, rows, ['', _('Total'), '', '', '', '', '', self._sum(rows, 7),
                                                           self._sum(rows, 8), self._sum(rows, 9), '',
                                                           self._sum(rows, 11), '', ''])], {
            'Occupancy %': KPI_DEFINITIONS['physical_occupancy'], 'Value': KPI_DEFINITIONS['value']}

    def _data_ownership(self, props):
        rows = []
        for p in props.sudo():
            for o in p.ownership_ids:
                rows.append([p.code, p.name, o.owner_id.name, dict(o._fields['role'].selection)[o.role],
                             o.percentage, self._fmt_date(o.date_from), self._fmt_date(o.date_to),
                             _('Yes') if o.is_current else _('No')])
        vrows = []
        for p in props.sudo():
            for v in p.valuation_ids.sorted('date'):
                vrows.append([p.code, self._fmt_date(v.date), v.valuer_id.name or '',
                              dict(v._fields['method'].selection)[v.method], v.value,
                              dict(v._fields['state'].selection)[v.state]])
        return [self._mk_table(_('Ownership History'), ['Code', 'Property', 'Owner', 'Role', '%', 'From', 'To', 'Current'], rows),
                self._mk_table(_('Valuation History'), ['Code', 'Date', 'Valuer', 'Method', 'Value', 'Status'], vrows)], {
            'Current valuation': KPI_DEFINITIONS['value']}

    def _data_occupancy(self, props):
        domain = [('property_id', 'in', props.ids)]
        if self.only_vacant:
            domain += [('occupancy_status', '=', 'vacant'), ('is_lettable', '=', True)]
        units = self.env['re.unit'].sudo().search(domain)
        rows = [[u.property_id.code, u.building_id.name or '', u.floor_id.name or '', u.name,
                 dict(u._fields['unit_type'].selection)[u.unit_type], round(u.area_sqm, 2),
                 _('Yes') if u.is_lettable else _('No'), dict(u._fields['occupancy_status'].selection)[u.occupancy_status],
                 dict(u._fields['rental_status'].selection).get(u.rental_status, ''), u.tenant_id.name or '',
                 self._fmt_date(u.lease_end_date), u.market_rent, u.current_rent, u.vacancy_days] for u in units]
        cols = ['Property', 'Building', 'Floor', 'Unit', 'Type', 'Area m²', 'Rentable', 'Occupancy', 'Rental Status',
                'Tenant', 'Lease End', 'Market Rent', 'Current Rent', 'Days Vacant']
        return [self._mk_table(_('Units'), cols, rows, ['', '', '', _('Total'), '', self._sum(rows, 5), '', '', '', '', '',
                                                     self._sum(rows, 11), self._sum(rows, 12), ''])], {
            'Occupancy': _('Physical occupancy status maintained by move-in / move-out.'),
            'Rental Status': _('Contractual status derived from leases (Let / Reserved / Available).'),
            'Days Vacant': _('Days since the unit became vacant.')}

    def _live_leases(self, props):
        return self.env['re.lease'].sudo().search([('property_id', 'in', props.ids),
                                                   ('state', 'in', ('active', 'expiring'))], order='property_id, name')

    def _data_rent_roll(self, props):
        rows = []
        for l in self._live_leases(props):
            next_esc = l.escalation_ids.filtered(lambda e: e.effective_date > fields.Date.context_today(self)
                                                 and e.state in ('approved', 'draft', 'to_approve'))[:1]
            rows.append([l.property_id.code, ', '.join(l.unit_ids.mapped('name')), l.name, l.tenant_id.name,
                         l.lease_type_id.name, round(l.leased_area_sqm, 2), self._fmt_date(l.date_start),
                         self._fmt_date(l.effective_end_date), l.current_rent, l.current_rent * 12,
                         dict(l._fields['billing_frequency'].selection)[l.billing_frequency], l.deposit_held,
                         l.amount_due, self._fmt_date(next_esc.effective_date) if next_esc else '',
                         _('Yes') if l.is_signed else _('No')])
        cols = ['Property', 'Units', 'Lease', 'Tenant', 'Type', 'Area m²', 'Start', 'End', 'Monthly Rent',
                'Annual Rent', 'Billing', 'Deposit Held', 'Balance Due', 'Next Escalation', 'Signed']
        return [self._mk_table(_('Rent Roll as at %s', self._fmt_date(fields.Date.context_today(self))), cols, rows,
                            ['', '', '', _('Total'), '', self._sum(rows, 5), '', '', self._sum(rows, 8),
                             self._sum(rows, 9), '', self._sum(rows, 11), self._sum(rows, 12), '', ''])], {
            'Monthly Rent': _('Base rent compounded with approved escalations effective today (before rent-free).'),
            'Balance Due': _('Open balance of posted invoices and credit notes of the lease.'),
            'Deposit Held': _('Received deposit amounts held as liability, not yet refunded.')}

    def _data_lease_expiry(self, props):
        today = fields.Date.context_today(self)
        leases = self.env['re.lease'].sudo().search([
            ('property_id', 'in', props.ids), ('state', 'in', ('active', 'expiring', 'expired')),
            ('effective_end_date', '<=', today + timedelta(days=self.expiry_days))], order='effective_end_date')
        rows = [[l.property_id.code, l.name, l.tenant_id.name, ', '.join(l.unit_ids.mapped('name')),
                 self._fmt_date(l.effective_end_date), (l.effective_end_date - today).days, l.current_rent,
                 l.notice_period_days, dict(l._fields['state'].selection)[l.state],
                 _('Renewal drafted') if l.renewal_lease_ids else ''] for l in leases]
        renewals = self.env['re.lease'].sudo().search([('property_id', 'in', props.ids), ('parent_lease_id', '!=', False),
                                                       ('create_date', '>=', self.date_from)])
        rrows = [[r.property_id.code, r.parent_lease_id.name, r.name, r.tenant_id.name,
                  r.parent_lease_id.current_rent, r.rent_amount,
                  100.0 * (r.rent_amount - r.parent_lease_id.current_rent) / r.parent_lease_id.current_rent
                  if r.parent_lease_id.current_rent else 0.0, dict(r._fields['state'].selection)[r.state]]
                 for r in renewals]
        return [self._mk_table(_('Leases expiring within %s days', self.expiry_days),
                            ['Property', 'Lease', 'Tenant', 'Units', 'End', 'Days Left', 'Monthly Rent', 'Notice (d)',
                             'Status', 'Renewal'], rows, ['', '', _('Total'), '', '', '', self._sum(rows, 6), '', '', '']),
                self._mk_table(_('Renewals'), ['Property', 'Previous Lease', 'Renewal', 'Tenant', 'Old Rent', 'New Rent',
                                            'Change %', 'Status'], rrows)], {
            'Expiring window': _('Effective end date (termination date or contractual end) within the window.')}

    def _data_escalation(self, props):
        escs = self.env['re.lease.escalation'].sudo().search([
            ('lease_id.property_id', 'in', props.ids), ('effective_date', '>=', self.date_from),
            ('effective_date', '<=', self.date_to + timedelta(days=self.expiry_days))], order='effective_date')
        rows = [[e.lease_id.property_id.code, e.lease_id.name, e.lease_id.tenant_id.name, self._fmt_date(e.effective_date),
                 dict(e._fields['method'].selection)[e.method], e.value, e.rent_before, e.rent_after,
                 dict(e._fields['state'].selection)[e.state], _('Yes') if e.contractual else _('No')] for e in escs]
        return [self._mk_table(_('Escalations'), ['Property', 'Lease', 'Tenant', 'Effective', 'Method', 'Value',
                                               'Rent Before', 'Rent After', 'Status', 'Contractual'], rows)], {
            'Status': _('Only Approved / Applied escalations are billed. Draft escalations past their date are '
                        'flagged by revenue assurance.')}

    def _data_rate_comparison(self, props):
        rows = []
        for l in self._live_leases(props):
            area = l.leased_area_sqm
            market = sum(l.unit_ids.mapped('market_rent'))
            rows.append([l.property_id.code, ', '.join(l.unit_ids.mapped('name')), l.tenant_id.name,
                         l.lease_type_id.name, round(area, 2), l.current_rent, market,
                         l.current_rent / area if area else 0.0, market / area if area else 0.0,
                         100.0 * (l.current_rent - market) / market if market else 0.0])
        return [self._mk_table(_('Contract vs Market Rent'), ['Property', 'Units', 'Tenant', 'Type', 'Area m²',
                                                           'Contract Rent', 'Market Rent', 'Contract /m²', 'Market /m²',
                                                           'Variance %'], rows)], {
            'Market Rent': _('Expected monthly rental value recorded on the units.')}

    def _data_rental_income(self, props):
        AML = self.env['account.move.line'].sudo()
        Analytics = self.env['re.analytics']
        domain = Analytics._rental_lines_domain(props.ids, self.date_from, self.date_to)
        data = AML._read_group(domain, ['re_property_id', 're_charge_type'], ['balance:sum'])
        labels = dict(self.env['account.move.line']._fields['re_charge_type'].selection)
        rows = [[p.code if p else _('(unallocated)'), labels.get(ct, ct or ''), -bal] for p, ct, bal in data]
        rows.sort()
        return [self._mk_table(_('Rental Income'), ['Property', 'Charge Type', 'Amount (untaxed)'], rows,
                            [_('Total'), '', self._sum(rows, 2)])], {'Amount': KPI_DEFINITIONS['invoiced']}

    def _data_tenant_ageing(self, props):
        Ageing = self.env['re.tenant.ageing'].sudo()
        rows_by = {}
        for r in Ageing.search([('property_id', 'in', props.ids)]):
            key = (r.partner_id.name, r.property_id.code or '')
            agg = rows_by.setdefault(key, [0.0] * 7)
            for i, f in enumerate(['amount_current', 'amount_1_30', 'amount_31_60', 'amount_61_90', 'amount_90_plus',
                                   'amount_disputed', 'amount_residual']):
                agg[i] += r[f]
        rows = [[k[0], k[1]] + v for k, v in sorted(rows_by.items())]
        cols = ['Tenant', 'Property', 'Current', '1-30', '31-60', '61-90', '90+', 'Disputed', 'Total']
        return [self._mk_table(_('Tenant Ageing as at %s', self._fmt_date(fields.Date.context_today(self))), cols, rows,
                            [_('Total'), ''] + [self._sum(rows, i) for i in range(2, 9)])], {
            'Buckets': _('Days past due date of each open receivable item. Disputed invoices are excluded from the '
                         'overdue buckets and shown separately. Current includes unallocated credits (negative).')}

    def _data_collection(self, props):
        Analytics = self.env['re.analytics']
        coll, total_receipts = Analytics._collections(props.ids, self.date_from, self.date_to)
        rows = []
        for p in props.sudo():
            due, paid = Analytics._collection_efficiency([p.id], self.date_from, self.date_to)
            rows.append([p.code, p.name, due, paid, 100.0 * paid / due if due else 0.0, coll.get(p.id, 0.0)])
        due_t, paid_t = self._sum(rows, 2), self._sum(rows, 3)
        return [self._mk_table(_('Collection Efficiency'), ['Code', 'Property', 'Due in Period', 'Paid (of due)',
                                                         'Efficiency %', 'Allocated Collections'], rows,
                            [_('Total'), '', due_t, paid_t, 100.0 * paid_t / due_t if due_t else 0.0,
                             self._sum(rows, 5)]),
                self._mk_table(_('Total tenant receipts in period'), ['Measure', 'Amount'],
                            [[_('All receipts (allocated and unallocated)'), total_receipts]])], {
            'Efficiency %': KPI_DEFINITIONS['collection_efficiency'], 'Allocated Collections': KPI_DEFINITIONS['collected'],
            'Total receipts': KPI_DEFINITIONS['total_collections']}

    def _data_property_income(self, props):
        AML = self.env['account.move.line'].sudo()
        Analytics = self.env['re.analytics']
        excluded, include_other = Analytics._accounts_by_policy(props.sudo().mapped('company_id'))
        rev_types = ('income', 'income_other') if include_other else ('income',)
        tables = []
        for p in props.sudo():
            domain = [('re_property_id', '=', p.id), ('parent_state', '=', 'posted'),
                      ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
            data = AML._read_group(domain + [('account_id.account_type', 'in', rev_types + ('expense',
                                                                                             'expense_direct_cost'))],
                                   ['account_id'], ['balance:sum'])
            rows = []
            rev = opex = 0.0
            for account, bal in sorted(data, key=lambda d: d[0].code or ''):
                if account.id in excluded:
                    rows.append([_('Excluded from NOI'), account.display_name, bal])
                    continue
                if account.account_type in rev_types:
                    rows.append([_('Revenue'), account.display_name, -bal])
                    rev += -bal
                else:
                    rows.append([_('Operating Expense'), account.display_name, -bal])
                    opex += bal
            capex = Analytics._capex([p.id], self.date_from, self.date_to)
            rows.append([_('Net Operating Income'), '', rev - opex])
            rows.append([_('Memo: Capital Expenditure (excluded)'), '', capex])
            tables.append(self._mk_table('%s - %s' % (p.code, p.name), ['Section', 'Account', 'Amount'], rows))
        return tables, {'NOI': KPI_DEFINITIONS['noi'],
                        'Sign': _('Revenue shown positive, expenses negative. Source: posted journal items analytically '
                                  'allocated to the property.')}

    def _data_property_comparison(self, props):
        data = self.env['re.analytics'].get_dashboard_data({
            'date_from': fields.Date.to_string(self.date_from), 'date_to': fields.Date.to_string(self.date_to),
            'portfolio_id': self.portfolio_id.id or False,
            'property_id': self.property_ids.id if len(self.property_ids) == 1 else False})
        allowed = set(props.ids)
        rows = [[r['code'], r['name'], r['type'], r['units'], round(r['occupancy'], 1), round(r['area_occupancy'], 1),
                 r['invoiced'], r['collected'], r['outstanding'], r['revenue'], r['opex'], r['noi'],
                 r['maintenance'], r['value'], round(r['net_yield'], 2), round(r['tenant_concentration'], 1),
                 round(r['avg_vacancy_days'], 0)] for r in data['comparison'] if r['id'] in allowed]
        cols = ['Code', 'Property', 'Type', 'Units', 'Occ. %', 'Area Occ. %', 'Invoiced', 'Collected', 'Outstanding',
                'Revenue', 'Opex', 'NOI', 'Maintenance', 'Value', 'Net Yield %', 'Top Tenant %', 'Avg Vacancy (d)']
        return [self._mk_table(_('Property Comparison (grouped by property category)'), cols, rows)], {
            'Occ. %': KPI_DEFINITIONS['physical_occupancy'], 'Area Occ. %': KPI_DEFINITIONS['area_occupancy'],
            'Invoiced': KPI_DEFINITIONS['invoiced'], 'Collected': KPI_DEFINITIONS['collected'],
            'NOI': KPI_DEFINITIONS['noi'], 'Net Yield %': KPI_DEFINITIONS['net_yield'],
            'Top Tenant %': _('Largest tenant share of rent invoiced (tenant concentration risk).')}

    def _data_deposit_liability(self, props):
        deps = self.env['re.security.deposit'].sudo().search([('property_id', 'in', props.ids),
                                                              ('state', 'not in', ('cancelled',))])
        rows = [[d.property_id.code, d.name, d.lease_id.name, d.tenant_id.name,
                 dict(d._fields['purpose'].selection)[d.purpose], d.amount, d.received_amount, d.held_amount,
                 d.deduction_total, dict(d._fields['state'].selection)[d.state]] for d in deps]
        return [self._mk_table(_('Deposits'), ['Property', 'Deposit', 'Lease', 'Tenant', 'Purpose', 'Required', 'Received',
                                            'Liability Held', 'Deductions', 'Status'], rows,
                            ['', '', '', _('Total'), '', self._sum(rows, 5), self._sum(rows, 6), self._sum(rows, 7),
                             self._sum(rows, 8), ''])], {
            'Liability Held': _('Deposits received and not yet released by a refund credit note. Recorded on the '
                                'configured deposit liability account, never as income.')}

    def _data_service_charge(self, props):
        budgets = self.env['re.service.charge.budget'].sudo().search([
            ('property_id', 'in', props.ids), ('date_from', '<=', self.date_to), ('date_to', '>=', self.date_from)])
        rows = [[b.name, b.building_id.display_name or b.property_id.code, self._fmt_date(b.date_from),
                 self._fmt_date(b.date_to), b.total_budget, b.total_actual, b.variance, round(b.variance_pct, 1),
                 b.total_billed, b.total_collected, b.landlord_void_share,
                 dict(b._fields['state'].selection)[b.state]] for b in budgets]
        lrows = []
        for b in budgets:
            for line in b.line_ids:
                lrows.append([b.name, line.name, line.budget_amount, line.actual_amount, line.variance])
        return [self._mk_table(_('Service-Charge Budgets'), ['Budget', 'Building', 'From', 'To', 'Budget', 'Actual',
                                                          'Variance', 'Var %', 'Billed', 'Collected', 'Vacant Share',
                                                          'Status'], rows),
                self._mk_table(_('Budget vs Actual by Category'), ['Budget', 'Category', 'Budget', 'Actual', 'Variance'],
                            lrows)], {
            'Actual': _('Posted expenditure on the mapped expense accounts allocated to the building/property in the '
                        'budget period.'),
            'Vacant Share': _('Actual cost share of units without a lease (landlord void cost).')}

    def _data_work_orders(self, props):
        wos = self.env['re.work.order'].sudo().search([
            ('property_id', 'in', props.ids), ('date_request', '>=', self.date_from),
            ('date_request', '<=', self.date_to)], order='date_request')
        labels = dict(self.env['re.work.order']._fields['state'].selection)
        rows = [[w.name, w.property_id.code, w.equipment_id.name or '', w.title,
                 dict(w._fields['maintenance_type'].selection)[w.maintenance_type], w.expenditure_type.upper(),
                 self._fmt_date(w.date_request), self._fmt_date(w.date_target), self._fmt_date(w.date_done),
                 w.contractor_id.name or w.technician_id.name or '', w.estimated_cost, w.approved_budget,
                 w.actual_cost, labels[w.state], _('Yes') if w.is_overdue else ''] for w in wos]
        return [self._mk_table(_('Work Orders'), ['WO', 'Property', 'Equipment', 'Problem', 'Type', 'Exp.', 'Requested',
                                               'Target', 'Done', 'Assigned', 'Proposed', 'Approved', 'Actual', 'Status',
                                               'Overdue'], rows,
                            ['', '', '', _('Total'), '', '', '', '', '', '', self._sum(rows, 10), self._sum(rows, 11),
                             self._sum(rows, 12), '', ''])], {
            'Actual': _('Posted vendor bills (untaxed) linked to the work order.')}

    def _data_pm_compliance(self, props):
        plans = self.env['re.maintenance.plan'].sudo().search([('property_id', 'in', props.ids)])
        rows = []
        for p in plans:
            wos = p.work_order_ids.filtered(lambda w: w.scheduled_date and self.date_from <= w.scheduled_date <= self.date_to)
            done = wos.filtered('date_done')
            on_time = done.filtered(lambda w: w.date_done <= w.scheduled_date)
            rows.append([p.property_id.code, p.name, p.equipment_id.name or '', len(wos), len(done), len(on_time),
                         100.0 * len(on_time) / len(wos) if wos else 0.0, self._fmt_date(p.next_date)])
        return [self._mk_table(_('Preventive Maintenance Compliance'), ['Property', 'Plan', 'Equipment', 'Scheduled',
                                                                     'Completed', 'On Time', 'Compliance %', 'Next Due'],
                            rows)], {'Compliance %': _('Work orders completed on or before the scheduled date ÷ work '
                                                       'orders scheduled in the period.')}

    def _data_asset_replacement(self, props):
        eqs = self.env['maintenance.equipment'].sudo().search([('re_property_id', 'in', props.ids)])
        rec_labels = dict(self.env['maintenance.equipment']._fields['re_recommendation'].selection)
        rows = [[e.re_asset_code or '', e.name, e.re_property_id.code, e.re_asset_category_id.name or '',
                 dict(e._fields['re_condition'].selection).get(e.re_condition, ''),
                 dict(e._fields['re_criticality'].selection).get(e.re_criticality, ''), round(e.re_age_years, 1),
                 round(e.re_remaining_life_years, 1), e.re_maintenance_cost_total, e.re_cost_12m,
                 e.re_expected_future_repair, e.re_replacement_cost, e.re_failures_12m, round(e.re_downtime_hours, 1),
                 rec_labels.get(e.re_recommendation, '')] for e in eqs]
        return [self._mk_table(_('Equipment'), ['Asset ID', 'Equipment', 'Property', 'Category', 'Condition', 'Criticality',
                                             'Age (y)', 'Remaining Life (y)', 'Cumulative Repairs', 'Repairs 12m',
                                             'Expected Future Repairs', 'Replacement Cost', 'Failures 12m',
                                             'Downtime (h)', 'Recommendation'], rows)], {
            'Expected Future Repairs': _('Last 12 months repair cost × remaining useful life (simple run-rate estimate).'),
            'Recommendation': _('Decision support only. Review for replacement when cumulative repairs reach the '
                                'category threshold of replacement cost, or past+future repairs exceed it, or a '
                                'critical asset has reached its useful life. Replacement requires management approval.')}

    def _data_contractor(self, props):
        partners = self.env['re.work.order'].sudo().search([('property_id', 'in', props.ids),
                                                            ('contractor_id', '!=', False)]).mapped(
            'contractor_id.commercial_partner_id')
        rows = [[p.name, p.re_jobs_assigned, p.re_jobs_completed, round(p.re_on_time_completion, 1),
                 round(p.re_avg_completion_days, 1), p.re_repeat_faults, p.re_complaints, round(p.re_avg_rating, 2),
                 p.re_approved_spend, p.re_actual_spend, round(p.re_cost_variance_pct, 1),
                 _('Yes') if p.re_is_compliant else (p.re_compliance_note or _('No'))] for p in partners.sudo()]
        return [self._mk_table(_('Contractor Performance'), ['Contractor', 'Assigned', 'Completed', 'On-time %',
                                                          'Avg Days', 'Repeat Faults', 'Poor Ratings', 'Avg Rating',
                                                          'Approved', 'Actual', 'Actual vs Approved %', 'Compliant'],
                            rows)], {
            'Repeat Faults': _('Corrective jobs on the same equipment within 90 days of a previous job.'),
            'Actual vs Approved %': _('(Actual billed − approved budget) ÷ approved budget across all jobs.')}

    def _data_investment(self, props):
        invs = self.env['re.investment'].search([])
        rows = [[i.code, i.name, i.version, i.scenario_name or '', dict(i._fields['state'].selection)[i.state],
                 i.total_investment, i.noi_year1, round(i.gross_yield, 2), round(i.net_yield, 2), i.npv, round(i.irr, 2),
                 round(i.equity_irr, 2), round(i.roi, 1), round(i.payback_years, 1) if i.payback_years else '-',
                 round(i.break_even_occupancy, 1)] for i in invs]
        return [self._mk_table(_('Investment Appraisals (projections)'), ['Code', 'Name', 'Ver.', 'Scenario', 'Status',
                                                                       'Investment', 'NOI Y1', 'Gross Yield %',
                                                                       'Net Yield %', 'NPV', 'IRR %', 'Equity IRR %',
                                                                       'ROI %', 'Payback (y)', 'Break-even Occ. %'],
                            rows)], {
            'Method': _('Projections based on the recorded assumptions (see re.investment documentation). These are '
                        'estimates, not actual results.')}

    # ------------------------------------------------------------------ outputs
    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('real_estate_lifecycle.action_report_re_management').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        import xlsxwriter
        data = self._get_report_data()
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        ws = wb.add_worksheet(data['title'][:31])
        bold = wb.add_format({'bold': True})
        title = wb.add_format({'bold': True, 'font_size': 14})
        head = wb.add_format({'bold': True, 'bg_color': '#DDE4EE', 'border': 1})
        num = wb.add_format({'num_format': '#,##0.00'})
        numb = wb.add_format({'num_format': '#,##0.00', 'bold': True, 'top': 1})
        r = 0
        ws.write(r, 0, data['title'], title)
        r += 1
        ws.write(r, 0, '%s | %s: %s - %s | %s %s' % (data['company'], _('Period'), data['date_from'], data['date_to'],
                                                     _('Currency'), data['currency']))
        r += 1
        ws.write(r, 0, _('Scope: %(s)s | Generated %(g)s by %(u)s', s=data['scope'], g=data['generated'], u=data['user']))
        r += 2
        for table in data['tables']:
            ws.write(r, 0, table['title'], bold)
            r += 1
            for c, col in enumerate(table['columns']):
                ws.write(r, c, col, head)
                ws.set_column(c, c, max(12, len(col) + 2))
            r += 1
            for row in table['rows']:
                for c, val in enumerate(row):
                    if isinstance(val, (int, float)):
                        ws.write_number(r, c, val, num)
                    else:
                        ws.write(r, c, val if val is not None else '')
                r += 1
            if table.get('totals'):
                for c, val in enumerate(table['totals']):
                    if isinstance(val, (int, float)):
                        ws.write_number(r, c, val, numb)
                    else:
                        ws.write(r, c, val or '', bold)
                r += 1
            r += 1
        ws.write(r, 0, _('Definitions'), bold)
        r += 1
        for k, v in data['definitions'].items():
            ws.write(r, 0, k, bold)
            ws.write(r, 1, v)
            r += 1
        wb.close()
        att = self.env['ir.attachment'].create({
            'name': '%s %s.xlsx' % (data['title'], data['date_to']),
            'datas': base64.b64encode(out.getvalue()),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % att.id, 'target': 'self'}
