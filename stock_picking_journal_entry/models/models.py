from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    journal_entry_ids = fields.Many2many(
        'account.move',
        string='Journal Entries',
        compute='_compute_journal_entry_ids',
    )

    journal_entry_count = fields.Integer(
        string='Journal Entries',
        compute='_compute_journal_entry_ids',
    )

    def _compute_journal_entry_ids(self):
        for picking in self:
            journal_entries = picking.move_ids.stock_valuation_layer_ids.mapped(
                'account_move_id'
            )

            picking.journal_entry_ids = journal_entries
            picking.journal_entry_count = len(journal_entries)

    def action_view_journal_entries(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entries',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('id', 'in', self.journal_entry_ids.ids),
            ],
            'context': {
                'create': False,
                'edit': False,
            },
        }