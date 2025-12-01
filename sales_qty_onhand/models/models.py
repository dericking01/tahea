from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    qty_on_hand = fields.Float(
        string="Qty On Hand",
        compute="_compute_qty_on_hand",
        store=False  # Set to True only if you want to store it
    )

    @api.depends('product_id')
    def _compute_qty_on_hand(self):
        for line in self:
            if line.product_id:
                # Get qty on hand based on selected warehouse
                warehouse = line.order_id.warehouse_id
                if warehouse:
                    # Check stock in the warehouse location
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', line.product_id.id),
                        ('location_id', 'child_of', warehouse.lot_stock_id.id)
                    ])
                    line.qty_on_hand = sum(quants.mapped('quantity'))
                else:
                    # General quantity on hand
                    line.qty_on_hand = line.product_id.qty_available
            else:
                line.qty_on_hand = 0
