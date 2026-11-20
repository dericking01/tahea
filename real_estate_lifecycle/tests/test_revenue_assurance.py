# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestRevenueAssurance(ReCommon):

    def _exc(self, code, **domain):
        dom = [('check_code', '=', code)] + [(k, '=', v) for k, v in domain.items()]
        return self.env['re.exception'].search(dom)

    def test_01_occupied_unit_without_lease(self):
        """Test 9: occupied unit without lease is detected, resolved and the
        dashboard updates."""
        unit = self.units[2]
        unit.occupancy_status = 'occupied'
        self.env['re.exception'].run_checks(['unit_occupied_no_lease'])
        exc = self._exc('unit_occupied_no_lease', unit_id=unit.id)
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc.state, 'new')
        self.assertEqual(exc.user_id, self.pm, 'property manager is responsible')
        data = self.env['re.analytics'].get_dashboard_data({'property_id': self.property.id})
        self.assertEqual(data['kpis']['open_exceptions'], 1)
        # rerun does not duplicate
        self.env['re.exception'].run_checks(['unit_occupied_no_lease'])
        self.assertEqual(len(self._exc('unit_occupied_no_lease', unit_id=unit.id)), 1)
        # resolve: register the lease
        self._activate(self._make_lease(units=unit))
        self.env['re.exception'].run_checks(['unit_occupied_no_lease'])
        self.assertEqual(exc.state, 'resolved')
        self.assertTrue(exc.auto_resolved)
        data = self.env['re.analytics'].get_dashboard_data({'property_id': self.property.id})
        self.assertEqual(data['kpis']['open_exceptions'], 0)

    def test_02_missing_invoice_and_unsigned(self):
        lease = self._activate(self._make_lease(start='2026-09-01'))
        self.env['re.exception'].run_checks(['lease_missing_invoice', 'lease_unsigned'])
        missing = self._exc('lease_missing_invoice', lease_id=lease.id)
        self.assertEqual(missing.state, 'new')
        self.assertTrue(self._exc('lease_unsigned', lease_id=lease.id))
        self._bill(lease, '2026-11-20')
        self.env['re.exception'].run_checks(['lease_missing_invoice'])
        self.assertEqual(missing.state, 'resolved')
        with self.assertRaises(UserError):
            lease.action_mark_signed()  # no signed document attached
        self.env['ir.attachment'].create({'name': 'signed.pdf', 'res_model': 're.lease', 'res_id': lease.id,
                                          'raw': b'%PDF-1.4'})
        lease.action_mark_signed()
        self.env['re.exception'].run_checks(['lease_unsigned'])
        self.assertEqual(self._exc('lease_unsigned', lease_id=lease.id).state, 'resolved')

    def test_03_unallocated_payment_and_unapproved_credit(self):
        lease = self._activate(self._make_lease())
        self._bill(lease, '2026-01-05')
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': self.tenant.id,
            'amount': 500_000, 'date': '2026-02-01', 'journal_id': self.company_data['default_journal_bank'].id})
        payment.action_post()
        self.env['re.exception'].run_checks(['payment_unallocated'])
        self.assertTrue(self._exc('payment_unallocated', partner_id=self.tenant.id),
                        'advance payment not allocated is flagged')
        invoice = self.env['account.move'].search([('re_lease_id', '=', lease.id), ('move_type', '=', 'out_invoice')])
        reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'reason': 'goodwill', 'journal_id': invoice.journal_id.id, 'date': '2026-02-02'})
        credit = self.env['account.move'].browse(reversal.refund_moves()['res_id'])
        credit.action_post()
        self.assertEqual(credit.re_lease_id, lease)
        self.env['re.exception'].run_checks(['unusual_adjustment'])
        exc = self._exc('unusual_adjustment', res_id=credit.id)
        self.assertTrue(exc, 'unapproved tenant credit note flagged')
        # with blocking enabled, posting requires approval
        self.company.re_block_unapproved_tenant_credit = True
        credit2 = invoice._reverse_moves()
        with self.assertRaises(UserError):
            credit2.action_post()
        credit2.with_user(self.accountant).action_re_request_adjustment_approval()
        credit2.with_user(self.fin_manager).action_re_approve_adjustment()
        credit2.action_post()
        self.assertEqual(credit2.state, 'posted')

    def test_04_termination_does_not_touch_posted_invoices(self):
        """Test 14 (part): operational workflows never modify posted accounting."""
        lease = self._activate(self._make_lease())
        self._bill(lease, '2026-06-05')
        invoices = self.env['account.move'].search([('re_lease_id', '=', lease.id)])
        snapshot = {m.id: (m.amount_total, m.state, m.name) for m in invoices}
        self.env['re.lease.terminate.wizard'].create({
            'lease_id': lease.id, 'termination_date': '2026-05-15', 'termination_type': 'early_tenant',
            'reason': 'Business closed'}).action_terminate()
        for m in invoices:
            self.assertEqual((m.amount_total, m.state, m.name), snapshot[m.id])
        exc = self._exc('termination_overbilled', lease_id=lease.id)
        self.assertEqual(len(exc), 2, 'May (partly) and June invoices flagged for credit-note review')
        self.assertTrue(any('2026-06-01' in d for d in exc.mapped('description')))

    def test_05_shared_building_issue(self):
        """Tenant CRM: several tenants reporting the same water problem are
        grouped into one shared building issue."""
        t2 = self.env['res.partner'].create({'name': 'Second Tenant'})
        l1 = self._activate(self._make_lease(units=self.units[0]))
        l2 = self._activate(self._make_lease(units=self.units[1], tenant=t2))
        water = self.env.ref('real_estate_lifecycle.complaint_category_water')
        k1 = self.env['re.tenant.ticket'].create({'subject': 'No water', 'partner_id': self.tenant.id,
                                                  'lease_id': l1.id, 'category_id': water.id})
        self.assertEqual(k1.building_id, self.building)
        self.assertFalse(k1.building_issue_id)
        k2 = self.env['re.tenant.ticket'].create({'subject': 'Low pressure', 'partner_id': t2.id,
                                                  'lease_id': l2.id, 'category_id': water.id})
        issue = k2.building_issue_id
        self.assertTrue(issue, 'shared issue detected')
        self.assertEqual(k1.building_issue_id, issue)
        self.assertEqual(issue.tenant_count, 2)
        issue.resolution = 'Booster pump replaced'
        issue.action_resolve()
        self.assertEqual(set((k1 | k2).mapped('state')), {'resolved'})

    def test_06_utility_recharge(self):
        lease = self._activate(self._make_lease(utility_recharge=True))
        tariff = self.env['re.utility.tariff'].create({'name': 'Water', 'utility_type': 'water', 'rate': 2000,
                                                       'uom_label': 'm3'})
        meter = self.env['re.meter'].create({'name': 'W-1', 'utility_type': 'water', 'property_id': self.property.id,
                                             'unit_id': self.units[0].id, 'tariff_id': tariff.id,
                                             'initial_reading': 100})
        r1 = self.env['re.meter.reading'].create({'meter_id': meter.id, 'date': '2026-02-01', 'current_reading': 130})
        self.assertEqual(r1.previous_reading, 100)
        self.assertEqual(r1.consumption, 30)
        self.assertEqual(r1.cost, 60_000)
        self.assertEqual(r1.lease_id, lease)
        self.assertTrue(r1.billable)
        self.env['re.exception'].run_checks(['utility_unbilled'])
        exc = self._exc('utility_unbilled', res_id=r1.id)
        self.assertTrue(exc)
        r1.action_bill()
        self.assertEqual(r1.state, 'billed')
        self.assertEqual(r1.invoice_id.amount_untaxed, 60_000)
        with self.assertRaises(UserError):
            r1.current_reading = 140
        self.env['re.exception'].run_checks(['utility_unbilled'])
        self.assertEqual(exc.state, 'resolved')
        # smart-meter integration point is idempotent and reports errors per reading
        meter.external_ref = 'SM-1'
        res = self.env['re.meter.reading'].api_submit_readings([
            {'meter_ref': 'SM-1', 'date': '2026-03-01', 'value': 150, 'external_id': 'x1'},
            {'meter_ref': 'SM-1', 'date': '2026-03-01', 'value': 150, 'external_id': 'x1'},
            {'meter_ref': 'UNKNOWN', 'date': '2026-03-01', 'value': 1, 'external_id': 'x2'}])
        self.assertEqual([r['status'] for r in res], ['ok', 'duplicate', 'error'])
