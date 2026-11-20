# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestDashboardInvestment(ReCommon):

    def test_01_dashboard_matches_records(self):
        """Test 12: dashboard figures equal the underlying records."""
        prop2 = self.env['re.property'].create({
            'name': 'Mbezi Shops', 'code': 'MBS', 'property_type_id': self.env.ref(
                'real_estate_lifecycle.property_type_retail').id, 'company_id': self.company.id,
            'purchase_price': 500_000_000, 'manager_id': self.pm.id})
        shop = self.env['re.unit'].create({'name': 'S1', 'property_id': prop2.id, 'unit_type': 'retail', 'area': 30,
                                           'market_rent': 1_500_000})
        l1 = self._activate(self._make_lease(units=self.units[0], rent=2_000_000))
        t2 = self.env['res.partner'].create({'name': 'Shop Tenant'})
        l2 = self.env['re.lease'].create({
            'tenant_id': t2.id, 'property_id': prop2.id, 'unit_ids': [(6, 0, shop.ids)], 'lease_type_id':
            self.lease_type.id, 'date_start': '2026-01-01', 'date_end': '2027-12-31', 'rent_amount': 1_500_000})
        self._activate(l2)
        for lease in (l1, l2):
            self._bill(lease, '2026-03-05')
        inv1 = self.env['account.move'].search([('re_lease_id', '=', l1.id), ('move_type', '=', 'out_invoice')])
        self._pay(inv1.sorted('invoice_date')[0], 2_000_000, '2026-01-10')
        wo = self.env['re.work.order'].create({
            'title': 'Pump', 'property_id': self.property.id, 'estimated_cost': 400_000,
            'technician_id': self.technician.id, 'contractor_id': self.partner_a.id, 'execution': 'contractor'})
        wo.with_user(self.pm).action_submit_approval()
        wo.with_user(self.pm).action_approve()  # within property-manager authority (no segregation rule)
        bill = self.env['account.move'].browse(wo.action_create_vendor_bill()['res_id'])
        bill.invoice_date = '2026-02-15'
        bill.action_post()

        data = self.env['re.analytics'].get_dashboard_data({'date_from': '2026-01-01', 'date_to': '2026-03-31'})
        k = data['kpis']
        props = self.property | prop2
        self.assertEqual(k['properties'], len(self.env['re.property'].search([('state', '!=', 'disposed')])))
        self.assertTrue(set(props.ids) <= set(data['property_ids']))
        self.assertEqual(k['units'], 6)
        self.assertEqual(k['occupied'], 2)
        self.assertAlmostEqual(k['physical_occupancy'], 100 * 2 / 6, places=2)
        self.assertAlmostEqual(k['invoiced'], 3 * 2_000_000 + 3 * 1_500_000)
        self.assertAlmostEqual(k['collected'], 2_000_000)
        all_invoices = self.env['account.move'].search([('re_lease_id', 'in', (l1 | l2).ids),
                                                        ('move_type', '=', 'out_invoice')])
        self.assertAlmostEqual(k['outstanding'], sum(all_invoices.mapped('amount_residual')))
        self.assertAlmostEqual(k['maintenance'], 400_000)
        self.assertAlmostEqual(k['revenue'], 10_500_000)
        self.assertAlmostEqual(k['opex'], 400_000)
        self.assertAlmostEqual(k['noi'], 10_100_000)
        row = next(r for r in data['comparison'] if r['id'] == prop2.id)
        self.assertAlmostEqual(row['invoiced'], 4_500_000)
        self.assertAlmostEqual(row['tenant_concentration'], 100.0)
        # building filter restricts unit KPIs
        data_b = self.env['re.analytics'].get_dashboard_data({'date_from': '2026-01-01', 'date_to': '2026-03-31',
                                                             'building_id': self.building.id})
        self.assertEqual(data_b['kpis']['units'], 5)
        # management reports render (PDF html + XLSX) from the same data
        for rtype in ('rent_roll', 'tenant_ageing', 'property_income', 'property_comparison', 'occupancy',
                      'collection', 'work_orders', 'asset_replacement', 'deposit_liability', 'lease_expiry'):
            wiz = self.env['re.report.wizard'].create({'report_type': rtype, 'date_from': '2026-01-01',
                                                       'date_to': '2026-03-31'})
            html = self.env['ir.actions.report']._render_qweb_html(
                'real_estate_lifecycle.action_report_re_management', wiz.ids)[0]
            self.assertIn(b'Definitions', html)
            action = wiz.action_export_xlsx()
            self.assertTrue(action['url'].startswith('/web/content/'))
        income = self.env['re.report.wizard'].create({'report_type': 'property_income', 'date_from': '2026-01-01',
                                                      'date_to': '2026-03-31', 'property_ids': [(6, 0, self.property.ids)]})
        table = income._get_report_data()['tables'][0]
        noi_row = next(r for r in table['rows'] if r[0] == 'Net Operating Income')
        self.assertAlmostEqual(noi_row[2], 3 * 2_000_000 - 400_000)

    def test_02_investment_appraisal(self):
        inv = self.env['re.investment'].create({
            'name': 'Mwenge Office Block', 'purchase_price': 1_000_000, 'annual_gross_rent': 100_000,
            'expected_occupancy': 100, 'annual_opex': 0, 'rent_growth': 0, 'opex_growth': 0,
            'discount_rate': 10, 'holding_years': 5, 'exit_cap_rate': 10, 'selling_costs_pct': 0})
        # perpetuity-like case: price = NOI / cap -> IRR = 10%, NPV at 10% = 0
        self.assertAlmostEqual(inv.irr, 10.0, places=3)
        self.assertAlmostEqual(inv.npv, 0.0, places=0)
        self.assertAlmostEqual(inv.gross_yield, 10.0)
        self.assertAlmostEqual(inv.net_yield, 10.0)
        self.assertAlmostEqual(inv.payback_years, 0.0)
        self.assertTrue(inv.payback_note)
        self.assertEqual(len(inv.cashflow_ids), 5)
        self.assertAlmostEqual(inv.break_even_occupancy, 0.0)
        inv.write({'annual_opex': 20_000, 'loan_amount': 500_000, 'interest_rate': 10, 'loan_term_years': 10})
        self.assertAlmostEqual(inv.noi_year1, 80_000)
        self.assertAlmostEqual(inv.annual_debt_service, 500_000 * 0.1 / (1 - 1.1 ** -10), places=2)
        self.assertAlmostEqual(inv.break_even_occupancy, 100 * (20_000 + inv.annual_debt_service) / 100_000, places=4)
        # approval locks assumptions; revisions keep the original case
        inv.action_submit()
        if inv.state == 'under_review':
            director = new_test_user(self.env, login='re_director', groups='real_estate_lifecycle.group_re_director',
                                     company_id=self.company.id, company_ids=[(6, 0, self.company.ids)])
            inv.with_user(director).action_approve()
        self.assertEqual(inv.state, 'approved')
        with self.assertRaises(UserError):
            inv.purchase_price = 2
        rev = self.env['re.investment'].browse(inv.action_create_revision()['res_id'])
        self.assertEqual(rev.version, 2)
        self.assertEqual(rev.original_id, inv)
        rev.purchase_price = 1_100_000
        self.assertEqual(inv.purchase_price, 1_000_000, 'approved case unchanged')
        sc = self.env['re.investment'].browse(inv.action_create_scenario()['res_id'])
        self.assertTrue(sc.is_scenario)
        with self.assertRaises(UserError):
            sc.action_submit()
