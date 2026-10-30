from odoo import _, api, fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    gw_receipt_confirm_type_id = fields.Many2one(
        'stock.picking.type', string='Receipt Confirmation Type', copy=False, readonly=True,
        help="Operation type of the transfers (transit -> destination) awaiting the receipt "
             "confirmation of the person in charge. Shown on the Inventory Overview.")

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        warehouses._gw_create_receipt_confirm_type()
        return warehouses

    def _get_picking_type_create_values(self, max_sequence):
        values, max_sequence = super()._get_picking_type_create_values(max_sequence)
        if 'int_type_id' in values:
            values['int_type_id']['gw_receipt_confirmation'] = True
        return values, max_sequence

    def _gw_get_receipt_confirm_type(self):
        self.ensure_one()
        if not self.gw_receipt_confirm_type_id:
            self._gw_create_receipt_confirm_type()
        return self.gw_receipt_confirm_type_id

    def _gw_create_receipt_confirm_type(self):
        # sudo: may be triggered by a stock user validating a transfer
        for warehouse in self.sudo().filtered(lambda w: not w.gw_receipt_confirm_type_id):
            transit = warehouse.company_id.internal_transit_location_id
            warehouse.gw_receipt_confirm_type_id = self.env['stock.picking.type'].sudo().create({
                'name': _('Receipt Confirmations'),
                'code': 'internal',
                'sequence_code': 'RC',
                'sequence': warehouse.in_type_id.sequence or 1,
                'warehouse_id': warehouse.id,
                'company_id': warehouse.company_id.id,
                'default_location_src_id': transit.id or warehouse.lot_stock_id.id,
                'default_location_dest_id': warehouse.lot_stock_id.id,
                'create_backorder': 'always',
                'active': warehouse.active,
            })
