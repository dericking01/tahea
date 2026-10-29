from odoo import fields
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAccountSequence(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.misc_journal = cls.company_data['default_journal_misc']
        cls.misc_journal.code = 'MISC'

    def _entry(self, date, post=True):
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': date,
            'line_ids': [
                (0, 0, {'name': 'debit', 'account_id': self.company_data['default_account_expense'].id, 'debit': 100.0}),
                (0, 0, {'name': 'credit', 'account_id': self.company_data['default_account_revenue'].id, 'credit': 100.0}),
            ],
        })
        if post:
            move.action_post()
        return move

    def test_backdate_posted_entry_takes_next_number_of_new_month(self):
        aug = [self._entry('2026-08-%02d' % day) for day in (3, 10, 20)]
        self.assertEqual(aug[-1].name, 'MISC/2026/08/0003')
        oct1 = self._entry('2026-10-01')
        oct2 = self._entry('2026-10-05')
        self.assertEqual(oct2.name, 'MISC/2026/10/0002')

        oct2.button_draft()
        with Form(oct2) as move_form:
            move_form.date = fields.Date.from_string('2026-08-25')
        oct2.action_post()

        self.assertEqual(oct2.name, 'MISC/2026/08/0004')
        self.assertEqual(oct1.name, 'MISC/2026/10/0001')
        names = self.env['account.move'].search([('journal_id', '=', self.misc_journal.id), ('state', '=', 'posted')]).mapped('name')
        self.assertEqual(len(names), len(set(names)), "No duplicated sequence numbers")

        # The number freed in October is the next one used there (no gap, no duplicate)
        oct3 = self._entry('2026-10-10')
        self.assertEqual(oct3.name, 'MISC/2026/10/0002')
        oct4 = self._entry('2026-10-11')
        self.assertEqual(oct4.name, 'MISC/2026/10/0003')

    def test_backdate_two_months_and_write_api(self):
        self._entry('2026-08-03')
        sep = self._entry('2026-09-03')
        oct1 = self._entry('2026-10-02')
        oct1.button_draft()
        oct1.date = '2026-09-15'
        oct1.action_post()
        self.assertEqual(sep.name, 'MISC/2026/09/0001')
        self.assertEqual(oct1.name, 'MISC/2026/09/0002')

        oct1.button_draft()
        oct1.date = '2026-08-30'
        oct1.action_post()
        self.assertEqual(oct1.name, 'MISC/2026/08/0002')

    def test_same_month_date_change_keeps_number(self):
        move = self._entry('2026-10-02')
        name = move.name
        move.button_draft()
        move.date = '2026-10-20'
        move.action_post()
        self.assertEqual(move.name, name)

    def test_new_draft_entry_backdated(self):
        self._entry('2026-08-03')
        self._entry('2026-08-04')
        draft = self._entry('2026-10-02', post=False)
        draft.date = '2026-08-28'
        draft.action_post()
        self.assertEqual(draft.name, 'MISC/2026/08/0003')
