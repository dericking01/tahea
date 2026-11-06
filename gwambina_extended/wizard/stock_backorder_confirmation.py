from odoo import api, fields, models


class StockBackorderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    gw_has_receipt_confirmation = fields.Boolean(compute='_compute_gw_receipt_confirmation')
    gw_can_return_remaining = fields.Boolean(compute='_compute_gw_receipt_confirmation')

    @api.depends('pick_ids')
    def _compute_gw_receipt_confirmation(self):
        for wizard in self:
            confirmations = wizard.pick_ids.filtered('gw_is_receipt_confirmation')
            wizard.gw_has_receipt_confirmation = bool(confirmations)
            wizard.gw_can_return_remaining = any(not p.gw_returned_to_source for p in confirmations)

    def process_cancel_backorder(self):
        """ Receipt confirmations: the missing goods are in transit and cannot simply be dropped.
        "No Backorder" puts them in a backorder that is immediately returned to the source location. """
        confirmations = self.pick_ids.filtered('gw_is_receipt_confirmation')
        picking_ids = self.env.context.get('button_validate_picking_ids')
        if not confirmations or not picking_ids:
            return super().process_cancel_backorder()
        pickings = self.env['stock.picking'].browse(picking_ids)
        self._check_less_quantities_than_expected(pickings)
        res = pickings.with_context(
            skip_backorder=True,
            picking_ids_not_to_backorder=(self.pick_ids - confirmations).ids,
        ).button_validate()
        backorders = self.env['stock.picking'].search([
            ('backorder_id', 'in', confirmations.filtered(lambda p: not p.gw_returned_to_source).ids),
            ('state', 'not in', ('done', 'cancel')),
        ])
        backorders.action_gw_return_to_source()
        return res
