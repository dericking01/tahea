from odoo import api, fields, models

# Native `account.move.payment_state` values (see PAYMENT_STATE_SELECTION in
# odoo/addons/account/models/account_move.py) folded into the three
# buckets required by the report, plus a catch-all "other" bucket for the
# rare states that don't represent a settlement outcome the report needs to
# highlight (a reversed invoice or one manually blocked from payment).
PAYMENT_STATE_BUCKETS = {
    'paid': 'paid',
    'in_payment': 'paid',
    'partial': 'partial',
    'not_paid': 'not_paid',
    'blocked': 'not_paid',
    'reversed': 'other',
    'invoicing_legacy': 'other',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    statement_cash_bank_type = fields.Selection(
        selection=[
            ('cash', "Cash"),
            ('bank', "Bank"),
            ('other', "Other / Unclassified"),
        ],
        string="Statement Payment Type",
        compute='_compute_statement_cash_bank_type',
        store=True,
        help="Classification used by the Custom Invoice Report to group "
             "invoices by 'Cash' or 'Bank'.\n\n"
             "Customer invoices are booked on a Sales journal, never on a "
             "Cash or Bank journal directly, so the invoice's own "
             "journal_id cannot be used to determine this. Instead this "
             "field looks at the journal(s) of the payments that actually "
             "reconciled the invoice (account.move.reconciled_payment_ids, "
             "Odoo's native link between an invoice and the payments that "
             "settle it), which is the accounting-correct representation "
             "of 'how was this invoice actually paid'.\n\n"
             "Rules:\n"
             "- No reconciled payment on a cash/bank journal (e.g. the "
             "invoice is not paid yet, or was settled through another "
             "journal type such as a misc./internal transfer entry): "
             "'other'.\n"
             "- All reconciled cash/bank payments share the same journal "
             "type: that type.\n"
             "- Payments split across both a cash and a bank journal "
             "(partial payments through different means): the invoice is "
             "classified under whichever journal type carried the larger "
             "cumulative payment amount, so each invoice is counted "
             "exactly once and totals never get split/duplicated across "
             "rows. Ties are assigned to 'bank'.",
    )
    statement_settlement_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Statement Settlement Journal",
        compute='_compute_statement_cash_bank_type',
        store=True,
        help="The specific Cash or Bank journal that actually settled this "
             "invoice (e.g. 'Selcom', 'CRDB Bank'), computed with the exact "
             "same dominant-amount logic as statement_cash_bank_type -- "
             "this is that field's journal-level detail, letting the "
             "Custom Invoice Report break Cash/Bank totals down per "
             "journal, not just per type. Empty when "
             "statement_cash_bank_type is 'other'.",
    )

    @api.depends(
        'move_type',
        'reconciled_payment_ids.journal_id',
        'reconciled_payment_ids.journal_id.type',
        'reconciled_payment_ids.amount',
    )
    def _compute_statement_cash_bank_type(self):
        for move in self:
            if move.move_type != 'out_invoice':
                move.statement_cash_bank_type = 'other'
                move.statement_settlement_journal_id = False
                continue

            relevant_payments = move.reconciled_payment_ids.filtered(
                lambda pay: pay.journal_id.type in ('cash', 'bank')
            )
            if not relevant_payments:
                move.statement_cash_bank_type = 'other'
                move.statement_settlement_journal_id = False
                continue

            amount_by_journal = {}
            for payment in relevant_payments:
                journal = payment.journal_id
                amount_by_journal[journal] = amount_by_journal.get(journal, 0.0) + payment.amount

            # Ties (equal cumulative amount) prefer a 'bank' journal, matching
            # statement_cash_bank_type's documented tie-break rule.
            dominant_journal = max(
                amount_by_journal.items(),
                key=lambda item: (item[1], item[0].type == 'bank'),
            )[0]

            move.statement_settlement_journal_id = dominant_journal
            move.statement_cash_bank_type = dominant_journal.type
