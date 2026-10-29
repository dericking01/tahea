from odoo import models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def _get_picking_type_create_values(self, max_sequence):
        values, max_sequence = super()._get_picking_type_create_values(max_sequence)
        if 'int_type_id' in values:
            values['int_type_id']['gw_receipt_confirmation'] = True
        return values, max_sequence
