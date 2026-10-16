# -*- coding: utf-8 -*-
from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values):
        move_values = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)
        sale_line = values.get('sale_line_id')
        if sale_line and self.picking_type_id.code == 'outgoing':
            location = self.env['sale.order.line'].browse(sale_line).order_id.product_location_id
            if location:
                move_values['location_id'] = location.id
        return move_values
