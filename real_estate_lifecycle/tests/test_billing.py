# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestBilling(ReCommon):

    def _rental_moves(self, lease):
        return self.env['account.move'].search([('re_lease_id', '=', lease.id), ('move_type', '=', 'out_invoice'),
                                                ('re_deposit_id', '=', False)])

    def test_01_monthly_billing_idempotent(self):
        """Test 3: monthly invoice in native Accounting; rerunning never duplicates."""
        lease = self._activate(self._make_lease())
        self._bill(lease, '2026-01-15')
        moves = self._rental_moves(lease)
        self.assertEqual(len(moves), 1)
        move = moves
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.partner_id, self.tenant)
        self.assertEqual(move.amount_untaxed, 2_000_000)
        self.assertEqual(str(move.invoice_date), '2026-01-01')
        line = move.invoice_line_ids
        self.assertEqual(line.re_charge_type, 'rent')
        self.assertEqual(line.re_property_id, self.property, 'analytic allocation to the property')
        self.assertEqual(line.re_building_id, self.building)
        self.assertEqual(line.product_id, self.env.ref('real_estate_lifecycle.product_re_rent'))
        # run again (same date and later run including the same obligation)
        self._bill(lease, '2026-01-15')
        self._bill(lease, '2026-01-31')
        self.assertEqual(len(self._rental_moves(lease)), 1, 'no duplicate invoice')
        self._bill(lease, '2026-03-05')
        self.assertEqual(len(self._rental_moves(lease)), 3)
        # the schedule obligation is unique at database level
        sl = lease.schedule_ids.filtered(lambda s: s.state == 'invoiced')[:1]
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['re.billing.schedule'].create({
                'lease_id': lease.id, 'obligation_key': sl.obligation_key, 'period_start': sl.period_start,
                'period_end': sl.period_end, 'invoice_date': sl.invoice_date, 'amount': 1, 'charge_type': 'rent',
                'name': 'dup'})
        # invoiced history cannot be deleted
        with self.assertRaises(UserError):
            sl.unlink()

    def test_02_partial_period_and_rent_free(self):
        lease = self._activate(self._make_lease(
            start='2026-01-15', rent=3_100_000, rent_free_date_from='2026-02-01', rent_free_date_to='2026-02-28'))
        jan = lease.schedule_ids.filtered(lambda s: str(s.period_start) == '2026-01-15')
        self.assertAlmostEqual(jan.amount, 3_100_000 * 17 / 31, places=0)
        feb = lease.schedule_ids.filtered(lambda s: str(s.period_start) == '2026-02-01')
        self.assertEqual(feb.amount, 0)
        self.assertEqual(feb.state, 'waived')
        self._bill(lease, '2026-03-02')
        self.assertEqual(len(self._rental_moves(lease)), 2, 'January and March billed, February rent-free')

    def test_03_quarterly_and_charges(self):
        lease = self._make_lease(billing_frequency='quarterly', rent=1_000_000)
        self.env['re.lease.charge'].create({'lease_id': lease.id, 'charge_type': 'parking', 'name': 'Parking bay',
                                            'amount': 100_000})
        self._activate(lease)
        self._bill(lease, '2026-01-10')
        move = self._rental_moves(lease)
        self.assertEqual(move.amount_untaxed, 3_300_000)
        self.assertEqual(set(move.invoice_line_ids.mapped('re_charge_type')), {'rent', 'parking'})

    def test_04_escalation(self):
        """Test 4: escalation applied on its effective date after approval; history preserved."""
        lease = self._make_lease(rent=1_000_000)
        self.env['re.lease.escalation'].create({'lease_id': lease.id, 'effective_date': '2026-04-01',
                                                'method': 'percent', 'value': 10})
        self._activate(lease)
        self._bill(lease, '2026-05-10')
        amounts = {str(m.invoice_date): m.amount_untaxed for m in self._rental_moves(lease)}
        self.assertEqual(amounts['2026-03-01'], 1_000_000)
        self.assertAlmostEqual(amounts['2026-04-01'], 1_100_000)
        self.assertAlmostEqual(amounts['2026-05-01'], 1_100_000)
        # non-contractual escalation on an active lease requires approval
        esc = self.env['re.lease.escalation'].create({'lease_id': lease.id, 'effective_date': '2026-07-01',
                                                      'method': 'new_amount', 'value': 1_500_000})
        july = lease.schedule_ids.filtered(lambda s: str(s.period_start) == '2026-07-01' and s.charge_type == 'rent')
        self.assertAlmostEqual(july.amount, 1_100_000, msg='draft escalation is not billed')
        self.env['re.exception'].run_checks(['escalation_not_applied'])
        exc = self.env['re.exception'].search([('check_code', '=', 'escalation_not_applied'), ('lease_id', '=', lease.id)])
        self.assertEqual(exc.state, 'new', 'passed escalation date without approval is flagged')
        esc.with_user(self.pm).action_submit()
        with self.assertRaises(Exception):
            esc.with_user(self.pm).action_approve()
        esc.with_user(self.approver).action_approve()
        self.assertAlmostEqual(july.amount, 1_500_000)
        self.assertEqual(amounts['2026-05-01'], self._rental_moves(lease).filtered(
            lambda m: str(m.invoice_date) == '2026-05-01').amount_untaxed, 'invoiced history unchanged')
        self.env['re.exception'].run_checks(['escalation_not_applied'])
        self.assertEqual(exc.state, 'resolved')
        self.assertTrue(exc.auto_resolved)
        with self.assertRaises(UserError):
            esc.value = 2_000_000

    def test_05_partial_payment_and_ageing(self):
        """Test 5: invoice 2,000,000; pay 1,200,000; balance 800,000 in ageing."""
        lease = self._activate(self._make_lease())
        self._bill(lease, '2026-01-05')
        move = self._rental_moves(lease)
        self.assertEqual(move.amount_total, 2_000_000)
        self._pay(move, 1_200_000, '2026-01-20')
        self.assertEqual(move.amount_residual, 800_000)
        self.assertEqual(move.payment_state, 'partial')
        self.env.flush_all()
        rows = self.env['re.tenant.ageing'].search([('partner_id', '=', self.tenant.id)])
        self.assertAlmostEqual(sum(rows.mapped('amount_residual')), 800_000)
        self.assertEqual(rows.property_id, self.property)
        self.assertAlmostEqual(sum(rows.mapped('amount_90_plus')) + sum(rows.mapped('amount_61_90')) +
                               sum(rows.mapped('amount_31_60')) + sum(rows.mapped('amount_1_30')) +
                               sum(rows.mapped('amount_current')), 800_000)
        self.assertEqual(lease.amount_due, 800_000)
        # dispute moves the balance out of confirmed overdue buckets
        move.re_dispute_state = 'open'
        self.env.flush_all()
        self.env['re.tenant.ageing'].invalidate_model()
        rows = self.env['re.tenant.ageing'].search([('partner_id', '=', self.tenant.id)])
        self.assertAlmostEqual(sum(rows.mapped('amount_disputed')), 800_000)
        self.assertAlmostEqual(sum(rows.mapped('amount_90_plus')), 0)

    def test_06_cancelled_invoice_rebilled_once(self):
        """Accounting integrity: a cancelled draft invoice frees the obligation and
        the next run bills it exactly once."""
        self.company.re_auto_post_invoices = False
        lease = self._activate(self._make_lease())
        self._bill(lease, '2026-01-05')
        move = self._rental_moves(lease)
        self.assertEqual(move.state, 'draft')
        move.button_cancel()
        sl = lease.schedule_ids.filtered(lambda s: str(s.period_start) == '2026-01-01')
        self.assertEqual(sl.state, 'pending')
        self._bill(lease, '2026-01-05')
        self._bill(lease, '2026-01-05')
        active = self._rental_moves(lease).filtered(lambda m: m.state != 'cancel')
        self.assertEqual(len(active), 1)

    def test_07_turnover_rent(self):
        lease = self._make_lease(rent=1_000_000, turnover_rent_enabled=True, turnover_rate=8.0,
                                 turnover_breakpoint=0.0, turnover_mode='greater_of')
        self._activate(lease)
        report = self.env['re.turnover.report'].create({'lease_id': lease.id, 'period_start': '2026-01-01',
                                                        'period_end': '2026-01-31', 'gross_sales': 20_000_000})
        report.action_verify()
        # 8% of 20M = 1.6M, less base rent 1.0M billed for January
        self.assertAlmostEqual(report.turnover_rent, 600_000)
        report.action_create_invoice()
        self.assertEqual(report.invoice_id.amount_untaxed, 600_000)
        with self.assertRaises(UserError):
            report.gross_sales = 1
