from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestStatementInvoiceReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.bank_journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)
        cls.cash_journal = cls.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', cls.company.id)], limit=1)
        cls.bank_journal_2 = cls.env['account.journal'].create({
            'name': 'Selcom Bank',
            'type': 'bank',
            'code': 'TSLC',
            'company_id': cls.company.id,
        })
        cls.income_account = cls.env['account.account'].search(
            [('account_type', '=', 'income'), ('company_ids', 'in', cls.company.id)], limit=1)

        # This demo database's Bank/Cash journals have no outstanding
        # ("payment_account_id") account configured on their payment method
        # lines, so registered payments never get their own journal entry
        # posted/reconciled (they stay stuck 'in_process' with an empty
        # move_id and the invoice residual never moves). That's a data-setup
        # gap in this sandbox, not something this report's logic controls,
        # so the fixture completes the configuration to get deterministic,
        # realistic paid/partial states to assert against.
        outstanding_account = cls.env['account.account'].create({
            'name': 'Test Outstanding Account',
            'code': 'TESTOUT01',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        for journal in (cls.bank_journal, cls.bank_journal_2, cls.cash_journal):
            (journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids).write({
                'payment_account_id': outstanding_account.id,
            })

    def _create_invoice(self, amount, invoice_date, move_type='out_invoice'):
        return self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Line',
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [(6, 0, [])],
                'account_id': self.income_account.id,
            })],
        })

    def _register_payment(self, invoice, amount, journal, payment_date=None):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'journal_id': journal.id,
            'amount': amount,
            'payment_date': payment_date or invoice.invoice_date,
        })
        wizard.action_create_payments()

    def test_01_domain_scope_excludes_draft_cancel_and_bills(self):
        posted_inv = self._create_invoice(100, '2026-01-15')
        posted_inv.action_post()

        draft_inv = self._create_invoice(50, '2026-01-16')

        cancel_inv = self._create_invoice(75, '2026-01-17')
        cancel_inv.action_post()
        cancel_inv.button_cancel()

        bill = self._create_invoice(60, '2026-01-18', move_type='in_invoice')
        bill.action_post()

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-01-01', 'date_to': '2026-01-31',
        })
        data = wizard._get_report_data()
        names = [line['name'] for line in data['invoices']]

        self.assertIn(posted_inv.name, names)
        self.assertNotIn(draft_inv.name, names)
        self.assertNotIn(cancel_inv.name, names)
        self.assertNotIn(bill.name, names)
        self.assertEqual(data['summary']['invoice_count'], 1)

    def test_02_payment_state_and_journal_classification(self):
        paid_bank = self._create_invoice(100, '2026-02-01')
        paid_bank.action_post()
        self._register_payment(paid_bank, 100, self.bank_journal)

        paid_cash = self._create_invoice(200, '2026-02-02')
        paid_cash.action_post()
        self._register_payment(paid_cash, 200, self.cash_journal)

        partial_bank = self._create_invoice(300, '2026-02-03')
        partial_bank.action_post()
        self._register_payment(partial_bank, 120, self.bank_journal)

        not_paid = self._create_invoice(400, '2026-02-04')
        not_paid.action_post()

        # A bank-journal payment settles the invoice as 'in_payment' until
        # the bank statement/transaction is reconciled (only cash and
        # instant-post journals go straight to 'paid') -- both states fold
        # into the report's "Paid" bucket via PAYMENT_STATE_BUCKETS.
        self.assertIn(paid_bank.payment_state, ('paid', 'in_payment'))
        self.assertEqual(paid_bank.statement_cash_bank_type, 'bank')
        self.assertIn(paid_cash.payment_state, ('paid', 'in_payment'))
        self.assertEqual(paid_cash.statement_cash_bank_type, 'cash')
        self.assertEqual(partial_bank.payment_state, 'partial')
        self.assertEqual(partial_bank.statement_cash_bank_type, 'bank')
        self.assertEqual(not_paid.payment_state, 'not_paid')
        self.assertEqual(not_paid.statement_cash_bank_type, 'other')

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-02-01', 'date_to': '2026-02-28',
        })
        data = wizard._get_report_data()

        self.assertEqual(data['summary']['invoice_count'], 4)
        self.assertAlmostEqual(data['summary']['total_amount'], 1000.0)
        self.assertAlmostEqual(data['summary']['paid_amount'], 100 + 200 + 120)
        self.assertAlmostEqual(data['summary']['outstanding_amount'], 180 + 400)

        bank_row = next(r for r in data['breakdown_rows'] if r['label'] == 'Bank')
        cash_row = next(r for r in data['breakdown_rows'] if r['label'] == 'Cash')
        self.assertEqual(bank_row['count'], 2)
        self.assertAlmostEqual(bank_row['amount'], 400.0)
        self.assertEqual(cash_row['count'], 1)
        self.assertAlmostEqual(cash_row['amount'], 200.0)

        # Both bank invoices were settled through the same journal, so the
        # per-journal drill-down should have exactly one row for it, and
        # that row's totals must reconcile with the type-level bank_row.
        bank_journal_rows = data['journal_rows']['bank']
        self.assertEqual(len(bank_journal_rows), 1)
        self.assertEqual(bank_journal_rows[0]['label'], self.bank_journal.name)
        self.assertEqual(bank_journal_rows[0]['count'], bank_row['count'])
        self.assertAlmostEqual(bank_journal_rows[0]['amount'], bank_row['amount'])

        cash_journal_rows = data['journal_rows']['cash']
        self.assertEqual(len(cash_journal_rows), 1)
        self.assertEqual(cash_journal_rows[0]['label'], self.cash_journal.name)

        self.assertEqual(data['unclassified']['count'], 1)
        self.assertAlmostEqual(data['unclassified']['amount'], 400.0)

        total_row = data['breakdown_total']
        # breakdown_total intentionally folds in the 'other'/unclassified
        # bucket too, so it reconciles exactly with the global summary count.
        self.assertEqual(total_row['count'], bank_row['count'] + cash_row['count'] + data['unclassified']['count'])
        # breakdown_total already folds in the 'other' bucket, so it must
        # reconcile exactly with the global summary total on its own.
        self.assertAlmostEqual(total_row['amount'], data['summary']['total_amount'])

    def test_03_mixed_journal_payment_dominant_type_no_double_count(self):
        invoice = self._create_invoice(300, '2026-03-01')
        invoice.action_post()
        self._register_payment(invoice, 50, self.cash_journal)
        self._register_payment(invoice, 200, self.bank_journal)

        self.assertEqual(invoice.statement_cash_bank_type, 'bank')

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
        })
        data = wizard._get_report_data()
        total_row = data['breakdown_total']
        self.assertEqual(total_row['count'], 1)
        self.assertAlmostEqual(total_row['amount'], 300.0)

    def test_03b_per_journal_breakdown_within_bank_type(self):
        """Two different bank journals should each get their own row under
        the 'Bank' type breakdown (e.g. distinguishing 'Bank' from 'Selcom
        Bank'), summing back exactly to the type-level bank_row -- this is
        the drill-down the report exists to provide."""
        inv_main_bank = self._create_invoice(600, '2026-03-10')
        inv_main_bank.action_post()
        self._register_payment(inv_main_bank, 600, self.bank_journal)

        inv_selcom_1 = self._create_invoice(200, '2026-03-11')
        inv_selcom_1.action_post()
        self._register_payment(inv_selcom_1, 200, self.bank_journal_2)

        inv_selcom_2 = self._create_invoice(50, '2026-03-12')
        inv_selcom_2.action_post()
        self._register_payment(inv_selcom_2, 20, self.bank_journal_2)  # partial

        self.assertEqual(inv_selcom_1.statement_settlement_journal_id, self.bank_journal_2)
        self.assertEqual(inv_selcom_2.statement_settlement_journal_id, self.bank_journal_2)
        self.assertEqual(inv_main_bank.statement_settlement_journal_id, self.bank_journal)

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-03-10', 'date_to': '2026-03-12',
        })
        data = wizard._get_report_data()
        bank_row = next(r for r in data['breakdown_rows'] if r['label'] == 'Bank')
        journal_rows = {r['label']: r for r in data['journal_rows']['bank']}

        self.assertEqual(set(journal_rows), {self.bank_journal.name, self.bank_journal_2.name})

        main_row = journal_rows[self.bank_journal.name]
        self.assertEqual(main_row['count'], 1)
        self.assertAlmostEqual(main_row['amount'], 600.0)

        selcom_row = journal_rows[self.bank_journal_2.name]
        self.assertEqual(selcom_row['count'], 2)
        self.assertAlmostEqual(selcom_row['amount'], 250.0)
        self.assertAlmostEqual(selcom_row['paid_amount'], 200.0)
        self.assertAlmostEqual(selcom_row['partial_amount'], 50.0)

        # Per-journal rows must reconcile exactly with the type-level row.
        self.assertEqual(sum(r['count'] for r in journal_rows.values()), bank_row['count'])
        self.assertAlmostEqual(sum(r['amount'] for r in journal_rows.values()), bank_row['amount'])

    def test_03c_date_basis_invoice_vs_payment(self):
        """An invoice dated outside the window but paid inside it should
        only show up under 'payment_date'; conversely an invoice dated
        inside the window but never paid should only show up under
        'invoice_date' (payment_date mode can never surface unpaid
        invoices, since there is no payment event to match on)."""
        backdated_but_paid_in_window = self._create_invoice(90, '2026-06-01')
        backdated_but_paid_in_window.action_post()
        self._register_payment(backdated_but_paid_in_window, 90, self.bank_journal, payment_date='2026-06-20')

        in_window_but_unpaid = self._create_invoice(70, '2026-06-15')
        in_window_but_unpaid.action_post()

        by_invoice_date = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'invoice_date', 'date_from': '2026-06-10', 'date_to': '2026-06-30',
        })
        names_by_invoice_date = [line['name'] for line in by_invoice_date._get_report_data()['invoices']]
        self.assertNotIn(backdated_but_paid_in_window.name, names_by_invoice_date)
        self.assertIn(in_window_but_unpaid.name, names_by_invoice_date)

        by_payment_date = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'payment_date', 'date_from': '2026-06-10', 'date_to': '2026-06-30',
        })
        names_by_payment_date = [line['name'] for line in by_payment_date._get_report_data()['invoices']]
        self.assertIn(backdated_but_paid_in_window.name, names_by_payment_date)
        self.assertNotIn(in_window_but_unpaid.name, names_by_payment_date)

    def test_03d_payment_date_splits_instalments_across_periods(self):
        """The exact scenario reported: an 80,000 invoice paid 30,000 on
        one day and 50,000 a week later must show only the instalment that
        actually falls within the selected window as its 'Paid' amount --
        not the invoice's full collected-to-date value -- when filtering
        by Payment Date. 'Amount Due' (current, live residual) and
        'Total Invoice Amount' are unaffected by the window."""
        invoice = self._create_invoice(80000, '2026-08-01')
        invoice.action_post()
        self._register_payment(invoice, 30000, self.bank_journal, payment_date='2026-08-10')
        self._register_payment(invoice, 50000, self.bank_journal, payment_date='2026-08-17')
        self.assertAlmostEqual(invoice.amount_residual, 0.0)

        def _get_line(wizard):
            data = wizard._get_report_data()
            line = next(l for l in data['invoices'] if l['name'] == invoice.name)
            return data, line

        wizard_17 = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'payment_date', 'date_from': '2026-08-17', 'date_to': '2026-08-17',
        })
        data_17, line_17 = _get_line(wizard_17)
        self.assertAlmostEqual(line_17['amount_paid'], 50000.0)
        self.assertAlmostEqual(line_17['amount_total'], 80000.0)
        self.assertAlmostEqual(line_17['amount_due'], 0.0)
        self.assertAlmostEqual(data_17['summary']['paid_amount'], 50000.0)
        bank_row_17 = next(r for r in data_17['breakdown_rows'] if r['label'] == 'Bank')
        self.assertAlmostEqual(bank_row_17['paid_amount'], 50000.0)
        # In Payment Date mode the breakdown table's "amount" column is
        # itself collected-in-window (see test_03e for why: an invoice can
        # span more than one journal, so attributing its full value would
        # double-count it across rows), so it matches paid_amount here.
        self.assertAlmostEqual(bank_row_17['amount'], 50000.0)

        wizard_10 = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'payment_date', 'date_from': '2026-08-10', 'date_to': '2026-08-10',
        })
        _, line_10 = _get_line(wizard_10)
        self.assertAlmostEqual(line_10['amount_paid'], 30000.0)

        wizard_both = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'payment_date', 'date_from': '2026-08-10', 'date_to': '2026-08-17',
        })
        _, line_both = _get_line(wizard_both)
        self.assertAlmostEqual(line_both['amount_paid'], 80000.0)

        # Invoice Date mode is unaffected by any of this: still the
        # all-time collected total regardless of which window is picked.
        wizard_invoice_date = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'invoice_date', 'date_from': '2026-08-01', 'date_to': '2026-08-01',
        })
        _, line_invoice_date = _get_line(wizard_invoice_date)
        self.assertAlmostEqual(line_invoice_date['amount_paid'], 80000.0)

    def test_03e_payment_date_splits_by_journal_within_same_window(self):
        """The exact scenario reported: an 80,000 invoice paid 40,000 via
        one bank journal and 40,000 via a cash journal, both within the
        same selected window, must appear as *two* detail rows -- one per
        contributing journal, each showing only its own amount -- instead
        of being collapsed into a single row under whichever journal
        happens to be the invoice's all-time "dominant" one."""
        invoice = self._create_invoice(80000, '2026-08-17')
        invoice.action_post()
        self._register_payment(invoice, 40000, self.bank_journal_2, payment_date='2026-08-17')  # "Lipa namba"-like
        self._register_payment(invoice, 40000, self.cash_journal, payment_date='2026-08-19')
        self.assertAlmostEqual(invoice.amount_residual, 0.0)

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_basis': 'payment_date', 'date_from': '2026-08-17', 'date_to': '2026-08-19',
        })
        data = wizard._get_report_data()
        lines = [l for l in data['invoices'] if l['name'] == invoice.name]
        self.assertEqual(len(lines), 2, "one detail row per contributing journal, not one collapsed row")

        by_journal = {l['settlement_journal']: l for l in lines}
        self.assertEqual(set(by_journal), {self.bank_journal_2.name, self.cash_journal.name})

        bank_line = by_journal[self.bank_journal_2.name]
        self.assertEqual(bank_line['cash_bank_type'], 'Bank')
        self.assertAlmostEqual(bank_line['amount_paid'], 40000.0)
        self.assertAlmostEqual(bank_line['amount_total'], 80000.0)  # full invoice value, repeated for context

        cash_line = by_journal[self.cash_journal.name]
        self.assertEqual(cash_line['cash_bank_type'], 'Cash')
        self.assertAlmostEqual(cash_line['amount_paid'], 40000.0)

        # The aggregate breakdown must attribute each journal's own share
        # correctly too (not lump all 80,000 under one type).
        bank_row = next(r for r in data['breakdown_rows'] if r['label'] == 'Bank')
        cash_row = next(r for r in data['breakdown_rows'] if r['label'] == 'Cash')
        self.assertAlmostEqual(bank_row['paid_amount'], 40000.0)
        self.assertAlmostEqual(cash_row['paid_amount'], 40000.0)

        # The invoice genuinely touched both types, so it is intentionally
        # counted once per type here (2 total) even though the Summary
        # still correctly reports exactly 1 unique invoice.
        self.assertEqual(bank_row['count'] + cash_row['count'], 2)
        self.assertEqual(data['summary']['invoice_count'], 1)
        self.assertTrue(data['has_split_settlements'])

        # Total collected (Summary KPI) must still add up to the full
        # 80,000 -- amounts are never lost or double-counted, only counts
        # legitimately diverge from unique-invoice counts in this mode.
        self.assertAlmostEqual(data['summary']['paid_amount'], 80000.0)

    def test_04_date_range_validation(self):
        with self.assertRaises(ValidationError):
            self.env['statement.invoice.report.wizard'].create({
                'date_from': '2026-05-10', 'date_to': '2026-05-01',
            })

    def test_05_empty_result_set(self):
        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2099-01-01', 'date_to': '2099-01-31',
        })
        data = wizard._get_report_data()
        self.assertEqual(data['summary']['invoice_count'], 0)
        self.assertEqual(data['invoices'], [])
        self.assertEqual(data['breakdown_total']['amount'], 0.0)

    def test_06_pdf_generation(self):
        invoice = self._create_invoice(150, '2026-04-01')
        invoice.action_post()
        self._register_payment(invoice, 150, self.bank_journal)

        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-04-01', 'date_to': '2026-04-30',
        })
        # Odoo automatically falls back from wkhtmltopdf to a plain HTML
        # render in test mode (test_enable) to avoid depending on the
        # wkhtmltopdf binary in CI; what matters here is that the QWeb
        # template itself renders without error for a populated dataset.
        content, report_type = self.env['ir.actions.report']._render_qweb_pdf(
            'custom_invoice_statement_report.action_report_statement_invoice', wizard.ids,
        )
        self.assertIn(report_type, ('pdf', 'html'))
        self.assertTrue(content)

    def test_07_xlsx_generation(self):
        self._create_invoice(150, '2026-04-01').action_post()
        wizard = self.env['statement.invoice.report.wizard'].create({
            'date_from': '2026-04-01', 'date_to': '2026-04-30',
        })
        data = wizard._get_report_data()
        xlsx_bytes = wizard._build_xlsx(data)
        self.assertTrue(xlsx_bytes.startswith(b'PK'))
