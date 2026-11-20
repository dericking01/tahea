# -*- coding: utf-8 -*-
"""Portfolio analytics service (dashboard, reports, investment comparison).

Security model: the set of properties is always searched AS THE CURRENT USER, so
record rules (company + property-level authorisation) apply. Financial
aggregates are then read with sudo but strictly limited to those property ids,
which lets investors / property managers see figures for their authorised
properties without granting them general accounting access.

KPI definitions are returned with the data and displayed on the dashboard."""
from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

RENT_TYPES = ('rent', 'turnover_rent', 'concession')
RENTAL_TYPES = ('rent', 'turnover_rent', 'concession', 'service_charge', 'service_charge_recon', 'parking',
                'marketing_levy', 'utility_fixed', 'utility', 'other')
REVENUE_TYPES = ('income',)
OPEX_TYPES = ('expense', 'expense_direct_cost')
CAPEX_TYPES = ('asset_fixed', 'asset_non_current')

KPI_DEFINITIONS = {
    'properties': 'Number of properties (not disposed) matching the filters that you are authorised to see.',
    'units': 'Rentable units: units marked "Rentable", excluding units flagged Unavailable (refurbishment/withdrawn).',
    'area': 'Sum of the area (converted to m²) of rentable units.',
    'occupied': 'Rentable units whose physical occupancy status is "Occupied".',
    'vacant': 'Rentable, available units that are not occupied.',
    'physical_occupancy': 'Occupied rentable units ÷ available rentable units. Excludes non-rentable and unavailable units.',
    'area_occupancy': 'Occupied rentable area ÷ available rentable area (m²).',
    'economic_occupancy': 'Effective rent revenue (posted rent, turnover rent and concessions, net of credit notes, dated '
                          'in the period) ÷ gross potential rent (expected monthly market rent of all available rentable '
                          'units × months in the period). Concessions reduce the numerator.',
    'invoiced': 'Posted rental-related invoice lines (rent, service charge, utilities, parking, levies, other fees) '
                'net of credit notes, untaxed, dated in the period. Security deposits are excluded.',
    'collected': 'Amounts reconciled during the period between tenant payments and rental invoices of the selected '
                 'properties (includes collection of prior-period arrears).',
    'total_collections': 'All tenant receipts posted in the period (allocated or not) for tenants of the selected '
                         'properties.',
    'outstanding': 'Open receivable balance of rental invoices (excluding unallocated credits) as of today, including '
                   'disputed amounts (shown separately).',
    'collection_efficiency': 'Current-period collection efficiency: for rental invoices due within the period, amount '
                             'paid ÷ amount due.',
    'noi': 'Net Operating Income = posted revenue on Income accounts − posted operating expenses on Expense and Cost of '
           'Revenue accounts, analytically allocated to the properties, dated in the period. Depreciation, financing, '
           'tax (accounts excluded in settings) and capital expenditure (fixed-asset accounts) are excluded.',
    'opex': 'Posted operating expenses (Expense / Cost of Revenue accounts, excluding excluded accounts) allocated to '
            'the properties in the period.',
    'value': 'Latest approved valuation of each property (purchase price if never valued).',
    'gross_yield': 'Annualised rental income invoiced ÷ property value.',
    'net_yield': 'Annualised NOI ÷ property value.',
    'expirations': 'Active leases whose effective end date falls within the next 90 days.',
    'maintenance': 'Posted vendor bills linked to work orders (untaxed, company currency) dated in the period.',
    'overdue_wo': 'Open work orders past their target completion date.',
    'service_charge': 'Service-charge budgets overlapping the period: budget vs actual expenditure vs billed vs '
                      'collected.',
    'capex_variance': 'Capital work orders requested in the period: actual billed − approved budget.',
}


class ReAnalytics(models.AbstractModel):
    _name = 're.analytics'
    _description = 'Real Estate Portfolio Analytics'

    # ------------------------------------------------------------------
    @api.model
    def _property_domain(self, filters):
        domain = [('state', '!=', 'disposed')]
        f = filters or {}
        if f.get('portfolio_id'):
            domain.append(('portfolio_id', '=', int(f['portfolio_id'])))
        if f.get('property_id'):
            domain.append(('id', '=', int(f['property_id'])))
        if f.get('property_type_id'):
            domain.append(('property_type_id', '=', int(f['property_type_id'])))
        if f.get('region'):
            domain.append(('region', '=ilike', f['region']))
        if f.get('manager_id'):
            domain.append(('manager_id', '=', int(f['manager_id'])))
        if f.get('company_id'):
            domain.append(('company_id', '=', int(f['company_id'])))
        return domain

    @api.model
    def _accounts_by_policy(self, companies):
        """Accounts excluded from NOI and whether other income counts, per company."""
        excluded = set()
        include_other = False
        for c in companies:
            excluded.update(c.re_noi_excluded_account_ids.ids)
            include_other = include_other or c.re_noi_include_other_income
        return excluded, include_other

    @api.model
    def _financials(self, property_ids, date_from, date_to, building_id=None):
        AML = self.env['account.move.line'].sudo()
        res = {'revenue': 0.0, 'opex': 0.0, 'noi': 0.0, 'maintenance': 0.0, 'by_property': defaultdict(
            lambda: {'revenue': 0.0, 'opex': 0.0, 'noi': 0.0, 'maintenance': 0.0})}
        if not property_ids:
            return res
        props = self.env['re.property'].sudo().browse(property_ids)
        excluded, include_other = self._accounts_by_policy(props.mapped('company_id'))
        rev_types = REVENUE_TYPES + (('income_other',) if include_other else ())
        domain = [('re_property_id', 'in', property_ids), ('parent_state', '=', 'posted'),
                  ('account_id.account_type', 'in', rev_types + OPEX_TYPES)]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if building_id:
            domain.append(('re_building_id', '=', building_id))
        if excluded:
            domain.append(('account_id', 'not in', list(excluded)))
        for prop, account, balance in AML._read_group(domain, ['re_property_id', 'account_id'], ['balance:sum']):
            bucket = res['by_property'][prop.id]
            if account.account_type in rev_types:
                bucket['revenue'] += -balance
                res['revenue'] += -balance
            else:
                bucket['opex'] += balance
                res['opex'] += balance
        mdomain = domain + [('move_id.re_work_order_id', '!=', False),
                            ('move_id.move_type', 'in', ('in_invoice', 'in_refund'))]
        for prop, balance in AML._read_group(mdomain, ['re_property_id'], ['balance:sum']):
            res['by_property'][prop.id]['maintenance'] += balance
            res['maintenance'] += balance
        for b in res['by_property'].values():
            b['noi'] = b['revenue'] - b['opex']
        res['noi'] = res['revenue'] - res['opex']
        return res

    @api.model
    def _capex(self, property_ids, date_from, date_to):
        domain = [('re_property_id', 'in', property_ids), ('parent_state', '=', 'posted'),
                  ('account_id.account_type', 'in', CAPEX_TYPES)]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        data = self.env['account.move.line'].sudo()._read_group(domain, [], ['balance:sum'])
        return data[0][0] or 0.0 if data else 0.0

    @api.model
    def _rental_lines_domain(self, property_ids, date_from, date_to, charge_types=RENTAL_TYPES, building_id=None):
        domain = [('move_id.re_property_id', 'in', property_ids), ('parent_state', '=', 'posted'),
                  ('display_type', '=', 'product'), ('re_charge_type', 'in', list(charge_types)),
                  ('move_id.move_type', 'in', ('out_invoice', 'out_refund'))]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if building_id:
            domain.append(('move_id.re_building_id', '=', building_id))
        return domain

    @api.model
    def _sum_rental(self, property_ids, date_from, date_to, charge_types=RENTAL_TYPES, building_id=None,
                    group_property=False):
        AML = self.env['account.move.line'].sudo()
        domain = self._rental_lines_domain(property_ids, date_from, date_to, charge_types, building_id)
        if group_property:
            return {p.id: -bal for p, bal in AML._read_group(domain, ['re_property_id'], ['balance:sum'])}
        data = AML._read_group(domain, [], ['balance:sum'])
        return -(data[0][0] or 0.0) if data else 0.0

    @api.model
    def _collections(self, property_ids, date_from, date_to, building_id=None):
        """Allocated collections (reconciled against rental invoices in the period)
        per property, and total receipts from the tenants of those properties."""
        Partial = self.env['account.partial.reconcile'].sudo()
        domain = [('debit_move_id.move_id.re_property_id', 'in', property_ids),
                  ('debit_move_id.move_id.move_type', '=', 'out_invoice'),
                  ('debit_move_id.move_id.re_deposit_id', '=', False),
                  ('max_date', '>=', date_from), ('max_date', '<=', date_to),
                  ('credit_move_id.move_id.move_type', '=', 'entry')]
        if building_id:
            domain.append(('debit_move_id.move_id.re_building_id', '=', building_id))
        by_prop = defaultdict(float)
        for p in Partial.search(domain):
            by_prop[p.debit_move_id.move_id.re_property_id.id] += p.amount
        tenants = self.env['re.lease'].sudo().search([('property_id', 'in', property_ids)]).mapped(
            'tenant_id.commercial_partner_id')
        receipts = self.env['account.move.line'].sudo()._read_group([
            ('partner_id', 'in', tenants.ids), ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'), ('move_id.move_type', '=', 'entry'), ('credit', '>', 0),
            ('date', '>=', date_from), ('date', '<=', date_to)], [], ['credit:sum']) if tenants else [(0.0,)]
        return by_prop, (receipts[0][0] or 0.0)

    @api.model
    def _collection_efficiency(self, property_ids, date_from, date_to, building_id=None):
        domain = [('re_property_id', 'in', property_ids), ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                  ('re_deposit_id', '=', False), ('invoice_date_due', '>=', date_from),
                  ('invoice_date_due', '<=', date_to)]
        if building_id:
            domain.append(('re_building_id', '=', building_id))
        moves = self.env['account.move'].sudo().search(domain)
        due = sum(moves.mapped('amount_total_signed'))
        paid = due - sum(moves.mapped('amount_residual_signed'))
        return due, paid

    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        filters = dict(filters or {})
        today = fields.Date.context_today(self)
        date_from = fields.Date.to_date(filters.get('date_from')) or today.replace(month=1, day=1)
        date_to = fields.Date.to_date(filters.get('date_to')) or today
        days = (date_to - date_from).days + 1
        months = days / 30.4375
        building_id = int(filters['building_id']) if filters.get('building_id') else None

        props = self.env['re.property'].search(self._property_domain(filters))   # as user -> record rules
        pids = props.ids
        unit_domain = [('property_id', 'in', pids), ('is_lettable', '=', True)]
        if building_id:
            unit_domain.append(('building_id', '=', building_id))
        units = self.env['re.unit'].sudo().search(unit_domain)
        available = units.filtered(lambda u: u.occupancy_status != 'unavailable')
        occupied = available.filtered(lambda u: u.occupancy_status == 'occupied')
        area_avail = sum(available.mapped('area_sqm'))
        area_occ = sum(occupied.mapped('area_sqm'))
        gpr = sum(available.mapped('market_rent')) * months

        fin = self._financials(pids, date_from, date_to, building_id)
        invoiced = self._sum_rental(pids, date_from, date_to, building_id=building_id)
        effective_rent = self._sum_rental(pids, date_from, date_to, RENT_TYPES, building_id)
        coll_by_prop, total_receipts = self._collections(pids, date_from, date_to, building_id)
        collected = sum(coll_by_prop.values())
        due, paid = self._collection_efficiency(pids, date_from, date_to, building_id)

        ageing_domain = [('property_id', 'in', pids), ('is_unallocated', '=', False), ('is_deposit', '=', False)]
        if building_id:
            ageing_domain.append(('building_id', '=', building_id))
        self.env.flush_all()
        Ageing = self.env['re.tenant.ageing'].sudo()
        Ageing.invalidate_model()
        ageing_rows = Ageing.search(ageing_domain)
        outstanding = sum(ageing_rows.mapped('amount_residual'))
        disputed = sum(ageing_rows.mapped('amount_disputed'))
        buckets = {k: sum(ageing_rows.mapped(f)) for k, f in [
            ('current', 'amount_current'), ('1_30', 'amount_1_30'), ('31_60', 'amount_31_60'),
            ('61_90', 'amount_61_90'), ('90_plus', 'amount_90_plus'), ('disputed', 'amount_disputed')]}

        value = sum(props.mapped('current_valuation'))
        annual = 365.0 / days if days else 0.0
        Lease = self.env['re.lease'].sudo()
        exp_domain = [('property_id', 'in', pids), ('state', 'in', ('active', 'expiring')),
                      ('effective_end_date', '<=', today + timedelta(days=90))]
        if building_id:
            exp_domain.append(('building_id', '=', building_id))
        expiring = Lease.search(exp_domain, order='effective_end_date')
        WO = self.env['re.work.order'].sudo()
        wo_domain = [('property_id', 'in', pids)]
        if building_id:
            wo_domain.append(('building_id', '=', building_id))
        overdue_wos = WO.search(wo_domain + [('is_overdue', '=', True)])
        open_wos = WO.search_count(wo_domain + [('state', 'not in', ('completed', 'tenant_confirmation', 'closed',
                                                                      'cancelled'))])
        capex_wos = WO.search(wo_domain + [('expenditure_type', '=', 'capex'), ('date_request', '>=', date_from),
                                           ('date_request', '<=', date_to), ('state', '!=', 'cancelled')])
        sc_domain = [('property_id', 'in', pids), ('date_from', '<=', date_to), ('date_to', '>=', date_from),
                     ('state', 'in', ('approved', 'applied', 'reconciled', 'closed'))]
        if building_id:
            sc_domain.append(('building_id', '=', building_id))
        budgets = self.env['re.service.charge.budget'].sudo().search(sc_domain)
        exceptions = self.env['re.exception'].sudo().search([('property_id', 'in', pids),
                                                             ('state', 'in', ('new', 'investigating'))])

        # ---- property comparison ------------------------------------------------
        rent_by_prop = self._sum_rental(pids, date_from, date_to, building_id=building_id, group_property=True)
        tenant_rent = self.env['account.move.line'].sudo()._read_group(
            self._rental_lines_domain(pids, date_from, date_to, RENT_TYPES, building_id),
            ['re_property_id', 'partner_id'], ['balance:sum'])
        top_tenant = defaultdict(float)
        for prop, partner, bal in tenant_rent:
            top_tenant[prop.id] = max(top_tenant[prop.id], -bal)
        out_by_prop = defaultdict(float)
        for row in ageing_rows:
            out_by_prop[row.property_id.id] += row.amount_residual
        comparison = []
        for prop in props.sudo():
            p_units = available.filtered(lambda u: u.property_id == prop)
            p_occ = p_units.filtered(lambda u: u.occupancy_status == 'occupied')
            p_area = sum(p_units.mapped('area_sqm'))
            pf = fin['by_property'].get(prop.id, {'revenue': 0.0, 'opex': 0.0, 'noi': 0.0, 'maintenance': 0.0})
            p_rent = rent_by_prop.get(prop.id, 0.0)
            vacant = p_units - p_occ
            comparison.append({
                'id': prop.id, 'code': prop.code, 'name': prop.name, 'type': prop.property_type_id.name,
                'category': prop.category, 'region': prop.region or '', 'units': len(p_units),
                'occupancy': 100.0 * len(p_occ) / len(p_units) if p_units else 0.0,
                'area_occupancy': 100.0 * sum(p_occ.mapped('area_sqm')) / p_area if p_area else 0.0,
                'invoiced': p_rent, 'collected': coll_by_prop.get(prop.id, 0.0),
                'outstanding': out_by_prop.get(prop.id, 0.0),
                'revenue': pf['revenue'], 'opex': pf['opex'], 'noi': pf['noi'], 'maintenance': pf['maintenance'],
                'value': prop.current_valuation,
                'net_yield': 100.0 * pf['noi'] * annual / prop.current_valuation if prop.current_valuation else 0.0,
                'noi_per_sqm': pf['noi'] / p_area if p_area else 0.0,
                'tenant_concentration': 100.0 * top_tenant.get(prop.id, 0.0) / p_rent if p_rent else 0.0,
                'avg_vacancy_days': sum(vacant.mapped('vacancy_days')) / len(vacant) if vacant else 0.0,
            })
        comparison.sort(key=lambda r: (r['category'] or '', -r['noi']))

        currency = self.env.company.currency_id
        kpis = {
            'properties': len(props), 'units': len(available), 'area': area_avail,
            'occupied': len(occupied), 'vacant': len(available) - len(occupied),
            'physical_occupancy': 100.0 * len(occupied) / len(available) if available else 0.0,
            'area_occupancy': 100.0 * area_occ / area_avail if area_avail else 0.0,
            'economic_occupancy': 100.0 * effective_rent / gpr if gpr else 0.0,
            'gpr': gpr, 'effective_rent': effective_rent,
            'invoiced': invoiced, 'collected': collected, 'total_collections': total_receipts,
            'outstanding': outstanding, 'disputed': disputed,
            'collection_efficiency': 100.0 * paid / due if due else 0.0, 'due_in_period': due,
            'paid_in_period': paid,
            'revenue': fin['revenue'], 'opex': fin['opex'], 'noi': fin['noi'],
            'value': value,
            'gross_yield': 100.0 * invoiced * annual / value if value else 0.0,
            'net_yield': 100.0 * fin['noi'] * annual / value if value else 0.0,
            'expirations': len(expiring), 'maintenance': fin['maintenance'],
            'overdue_wo': len(overdue_wos), 'open_wo': open_wos,
            'sc_budget': sum(budgets.mapped('total_budget')), 'sc_actual': sum(budgets.mapped('total_actual')),
            'sc_billed': sum(budgets.mapped('total_billed')), 'sc_collected': sum(budgets.mapped('total_collected')),
            'capex_approved': sum(capex_wos.mapped('approved_budget')),
            'capex_actual': sum(capex_wos.mapped('actual_cost')),
            'capex_variance': sum(capex_wos.mapped('actual_cost')) - sum(capex_wos.mapped('approved_budget')),
            'capex_accounts': self._capex(pids, date_from, date_to),
            'open_exceptions': len(exceptions),
            'exception_amount': sum(exceptions.mapped('amount')),
        }
        kpis = {key: (val + 0.0 if isinstance(val, float) else val) for key, val in kpis.items()}  # no -0.0
        top_arrears = defaultdict(float)
        for row in ageing_rows:
            if row.days_overdue > 0 and not row.is_disputed:
                top_arrears[row.partner_id] += row.amount_residual
        arrears = sorted(top_arrears.items(), key=lambda kv: -kv[1])[:8]
        sev_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        return {
            'currency': {'symbol': currency.symbol, 'position': currency.position, 'name': currency.name,
                         'decimals': currency.decimal_places},
            'period': {'date_from': fields.Date.to_string(date_from), 'date_to': fields.Date.to_string(date_to),
                       'days': days},
            'kpis': kpis,
            'definitions': KPI_DEFINITIONS,
            'property_ids': pids,
            'ageing': buckets,
            'comparison': comparison,
            'expiring': [{'id': l.id, 'name': l.name, 'tenant': l.tenant_id.name, 'property': l.property_id.name,
                          'end': fields.Date.to_string(l.effective_end_date), 'rent': l.current_rent,
                          'days': (l.effective_end_date - today).days} for l in expiring[:10]],
            'arrears': [{'id': p.id, 'name': p.name, 'amount': amt} for p, amt in arrears],
            'exceptions': [{'id': e.id, 'name': e.name, 'check': dict(e._fields['check_code'].selection)[e.check_code],
                            'severity': e.severity, 'property': e.property_id.name or '',
                            'amount': e.amount, 'user': e.user_id.name or '', 'description': e.description or ''}
                           for e in sorted(exceptions, key=lambda e: (sev_order.get(e.severity, 9), -e.id))[:12]],
            'overdue_wos': [{'id': w.id, 'name': w.name, 'title': w.title, 'property': w.property_id.name,
                             'target': fields.Date.to_string(w.date_target), 'priority': w.priority}
                            for w in overdue_wos[:10]],
            'filters_meta': self._filters_meta(),
        }

    @api.model
    def _filters_meta(self):
        props = self.env['re.property'].search([('state', '!=', 'disposed')])
        return {
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'portfolios': [{'id': p.id, 'name': p.name} for p in self.env['re.portfolio'].search([])],
            'properties': [{'id': p.id, 'name': '%s %s' % (p.code, p.name)} for p in props],
            'buildings': [{'id': b.id, 'name': b.display_name, 'property_id': b.property_id.id}
                          for b in self.env['re.building'].search([('property_id', 'in', props.ids)])],
            'types': [{'id': t.id, 'name': t.name} for t in self.env['re.property.type'].search([])],
            'regions': sorted(set(r for r in props.mapped('region') if r)),
            'managers': [{'id': u.id, 'name': u.name} for u in props.mapped('manager_id')],
        }
