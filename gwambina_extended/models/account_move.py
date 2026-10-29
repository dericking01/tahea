from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('posted_before', 'state', 'journal_id', 'date', 'move_type', 'origin_payment_id')
    def _compute_name(self):
        # Standard Odoo only resets the number of entries that were never posted. An entry that
        # was posted once, reset to draft and re-dated keeps its old number (e.g. MISC/2026/10/0002
        # on an August date) and then fails the date/sequence constraint. Clear it instead, so the
        # next number of the new period (e.g. MISC/2026/08/0242) is assigned when it is posted:
        # at that point the move is covered by the unique (name, journal) index, so no duplicates.
        for move in self:
            if (
                move.state == 'draft'
                and move.posted_before
                and move.name
                and move.name != '/'
                and not move._sequence_matches_date()
            ):
                move.name = False
        return super()._compute_name()
