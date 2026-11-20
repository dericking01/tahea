# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestDepositServiceCharge(ReCommon):

    def test_01_security_deposit_liability_and_refund(self):
        """Test 6: deposit held as liability (never income); authorised refund."""
        lease = self._activate(self._make_lease(deposit_amount=3_000_000))
        deposit = lease.deposit_ids
        self.assertEqual(deposit.state, 'draft')
        deposit.action_create_invoice()
        inv = deposit.invoice_id
        self.assertEqual(inv.state, 'posted')
        credit_lines = inv.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(credit_lines.account_id, self.deposit_account)
        self.assertFalse(inv.line_ids.filtered(lambda l: l.account_id.internal_group == 'income'),
                         'no income recognised for a refundable deposit')
        self._pay(inv, 3_000_000, '2026-01-05')
        self.assertEqual(deposit.state, 'held')
        self.assertEqual(deposit.held_amount, 3_000_000)
        fin = self.env['re.analytics']._financials(self.property.ids, None, None)
        self.assertEqual(fin['revenue'], 0, 'deposit excluded from NOI revenue')
        balance = sum(self.env['account.move.line'].search([
            ('account_id', '=', self.deposit_account.id), ('parent_state', '=', 'posted')]).mapped('balance'))
        self.assertEqual(balance, -3_000_000, 'liability credited')
        # refund only after the lease has ended
        with self.assertRaises(UserError):
            deposit.with_user(self.pm).action_request_refund()
        self.env['re.lease.terminate.wizard'].create({
            'lease_id': lease.id, 'termination_date': '2026-06-30', 'termination_type': 'mutual',
            'reason': 'End'}).action_terminate()
        self.env['re.deposit.deduction'].create({'deposit_id': deposit.id, 'name': 'Broken window', 'amount': 500_000})
        deposit.with_user(self.pm).action_request_refund()
        self.assertEqual(deposit.state, 'refund_requested')
        with self.assertRaises(AccessError):
            deposit.with_user(self.pm).action_approve_refund()
        with self.assertRaises(UserError):
            deposit.action_create_refund()
        deposit.with_user(self.fin_manager).action_approve_refund()
        self.assertEqual(deposit.state, 'refund_approved')
        deposit.action_create_refund()
        refund = deposit.refund_move_id
        self.assertEqual(refund.move_type, 'out_refund')
        self.assertEqual(refund.state, 'posted')
        self.assertEqual(refund.amount_total, 2_500_000)
        liab = refund.line_ids.filtered(lambda l: l.account_id == self.deposit_account)
        self.assertEqual(liab.debit, 3_000_000, 'full liability released')
        ded = refund.line_ids.filtered(lambda l: l.account_id == self.deduction_account)
        self.assertEqual(ded.credit, 500_000)
        self.assertEqual(deposit.state, 'refunded')
        self.assertEqual(deposit.held_amount, 0)

    def test_02_service_charge_ten_tenants(self):
        """Test 7: 10 tenants, TZS 50M budget allocated by area, actual expenditure,
        billing, collection, variance and reconciliation."""
        units = self.env['re.unit'].create([{
            'name': 'SC-%02d' % i, 'property_id': self.property.id, 'building_id': self.building.id,
            'unit_type': 'office', 'area': 100 + 20 * i, 'market_rent': 1_000_000} for i in range(10)])
        # remove the five fixture units from scope (excluded basis)
        self.units.write({'service_charge_basis': 'excluded'})
        leases = self.env['re.lease']
        for i, unit in enumerate(units):
            tenant = self.env['res.partner'].create({'name': 'Tenant %02d' % i})
            leases |= self._activate(self._make_lease(units=unit, tenant=tenant, rent=1_000_000))
        expense = self.env['account.account'].create({
            'name': 'Building Cleaning & Security', 'code': 'SCX01', 'account_type': 'expense',
            'company_ids': [(6, 0, self.company.ids)]})
        budget = self.env['re.service.charge.budget'].create({
            'name': 'SC 2026 Block A', 'property_id': self.property.id, 'building_id': self.building.id,
            'date_from': '2026-01-01', 'date_to': '2026-12-31', 'allocation_basis': 'area',
            'line_ids': [(0, 0, {'name': 'Cleaning & security', 'account_ids': [(6, 0, expense.ids)],
                                 'budget_amount': 50_000_000})]})
        budget.action_compute_allocation()
        self.assertEqual(len(budget.allocation_ids), 10)
        self.assertAlmostEqual(sum(budget.allocation_ids.mapped('share_pct')), 100.0, places=4)
        total_area = sum(units.mapped('area_sqm'))
        first = budget.allocation_ids.filtered(lambda a: a.unit_id == units[0])
        self.assertAlmostEqual(first.budget_share, 50_000_000 * units[0].area_sqm / total_area, places=0)
        budget.with_user(self.pm).action_submit()
        self.assertEqual(budget.state, 'to_approve')
        budget.with_user(self.fin_manager).action_approve()
        budget.action_apply_to_leases()
        budget.action_apply_to_leases()  # idempotent
        self.assertEqual(budget.state, 'applied')
        for lease in leases:
            self.assertEqual(len(lease.charge_ids.filtered(lambda c: c.charge_type == 'service_charge')), 1)
        # bill January for all tenants
        self.env['re.billing.schedule']._cron_generate_rental_invoices(
            date(2026, 1, 15), leases.ids)
        self.env.invalidate_all()
        self.assertAlmostEqual(budget.total_billed, 50_000_000 / 12, places=-1)
        # collection: first tenant pays January in full
        inv = self.env['account.move'].search([('re_lease_id', '=', first.lease_id.id), ('move_type', '=', 'out_invoice')])
        self._pay(inv, inv.amount_total, '2026-01-20')
        self.env.invalidate_all()
        self.assertAlmostEqual(first.collected_amount, first.billed_amount, places=0)
        # actual expenditure 60M posted on the mapped account, allocated to the building
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner_a.id, 'invoice_date': '2026-03-31',
            'invoice_line_ids': [(0, 0, {'name': 'Cleaning contract', 'account_id': expense.id, 'quantity': 1,
                                         'price_unit': 60_000_000, 'tax_ids': [(6, 0, [])],
                                         'analytic_distribution': self.property._re_analytic_distribution(self.building)})]})
        bill.action_post()
        self.assertEqual(bill.invoice_line_ids.re_building_id, self.building)
        self.env.invalidate_all()
        self.assertAlmostEqual(budget.total_actual, 60_000_000)
        self.assertAlmostEqual(budget.variance, 10_000_000)
        self.assertAlmostEqual(budget.variance_pct, 20.0)
        self.env['re.exception'].run_checks(['service_charge_overrun'])
        self.assertTrue(self.env['re.exception'].search([('check_code', '=', 'service_charge_overrun'),
                                                         ('res_id', '=', budget.id)]))
        # reconciliation: balancing charges = actual share - billed
        expected = sum(a.actual_share - a.billed_amount for a in budget.allocation_ids)
        budget.action_reconcile()
        self.assertEqual(budget.state, 'reconciled')
        self.assertEqual(len(budget.recon_move_ids), 10)
        self.assertTrue(all(m.state == 'draft' for m in budget.recon_move_ids), 'drafts for accountant review')
        self.assertAlmostEqual(sum(budget.recon_move_ids.mapped('amount_untaxed_signed')), expected, places=-1)
        report = self.env.ref('real_estate_lifecycle.action_report_service_charge')._render_qweb_html(
            'real_estate_lifecycle.report_service_charge', budget.ids)[0]
        self.assertIn(b'Service-Charge Reconciliation', report)
