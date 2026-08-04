from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    qty_on_hand = fields.Float(
        string='Qty On Hand',
        compute='_compute_qty_on_hand',
        digits='Product Unit of Measure',
        help="Quantity of this product currently on hand in the order's receiving warehouse.",
    )

    @api.depends('product_id', 'order_id.picking_type_id.warehouse_id')
    def _compute_qty_on_hand(self):
        for line in self:
            if not line.product_id or line.display_type:
                line.qty_on_hand = 0.0
                continue
            warehouse = line.order_id.picking_type_id.warehouse_id
            product = line.product_id.with_context(warehouse=warehouse.id) if warehouse else line.product_id
            line.qty_on_hand = product.qty_available
