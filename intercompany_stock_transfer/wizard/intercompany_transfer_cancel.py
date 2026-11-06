from odoo import fields, models


class IntercompanyStockTransferCancel(models.TransientModel):
    _name = 'intercompany.stock.transfer.cancel'
    _description = 'Cancel Inter-Company Stock Transfer'

    transfer_ids = fields.Many2many(
        'intercompany.stock.transfer', 'ict_cancel_wizard_transfer_rel', 'wizard_id', 'transfer_id',
        string='Transfers', required=True)
    reason = fields.Text('Reason', required=True)
    has_dispatched_stock = fields.Boolean(compute='_compute_has_dispatched_stock')

    def _compute_has_dispatched_stock(self):
        for wizard in self:
            wizard.has_dispatched_stock = any(
                line.qty_in_transit > 0 for line in wizard.transfer_ids.line_ids)

    def action_cancel(self):
        self.ensure_one()
        returns = self.transfer_ids._action_cancel(self.reason)
        if len(returns) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': returns.id,
            }
        return {'type': 'ir.actions.act_window_close'}
