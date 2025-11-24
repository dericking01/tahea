from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    on_hand = fields.Float(string='On-Hand', compute="_compute_on_hand", store=True)

    @api.depends('product_id')
    def _compute_on_hand(self):
        for rec in self:
            quant_ids = self.env['stock.quant'].search(
                [('location_id', 'child_of', rec.order_id.picking_type_id.default_location_dest_id.id),
                 ('product_id', '=', rec.product_id.id)])
            rec.on_hand = sum(quant_ids.mapped('quantity'))
