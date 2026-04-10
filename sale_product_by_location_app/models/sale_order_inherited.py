# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_multi_location = fields.Boolean(string='Multi Location')
    delivery_count = fields.Integer(string='Delivery Orders', compute='_compute_count')

    @api.constrains('order_line')
    def _check_product_location(self):
        for rec in self:
            product_vals = []
            for line_id in rec.order_line:
                if line_id.product_id and line_id.location_id:
                    vs = str(line_id.product_id.id) + str(line_id.location_id.id)
                    if vs in product_vals:
                        raise ValidationError(
                            _('Same product %s with same location %s is not allowed.') % (
                                line_id.product_id.name, line_id.location_id.name))
                    else:
                        product_vals.append(vs)

    def _compute_count(self):
        for order in self:
            picking = self.env['stock.picking'].search([('origin', '=', order.name)])
            order.delivery_count = len(picking)

    def action_view_multi_delivery(self):
        for order in self:
            return {
                'name': 'Delivery',
                'res_model': 'stock.picking',
                'domain': [('origin', '=', order.name)],
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
                'context': "{'create': False}"
            }

    def action_confirm(self):
        for rec in self:
            if rec.is_multi_location:
                location_dest_id = rec.partner_id.property_stock_customer
                for location_id in rec.order_line.mapped('location_id'):
                    move_vals = []
                    for line_id in rec.order_line.filtered(lambda line: line.location_id == location_id):
                        if line_id.product_id.type != 'service':
                            picking_line = {'product_id': line_id.product_id.id,
                                            'product_uom_qty': line_id.product_uom_qty,
                                            'name': line_id.product_id.name,
                                            'product_uom': line_id.product_uom.id,
                                            'location_id': location_id.id,
                                            'location_dest_id': location_dest_id.id}
                            move_vals.append((0, 0, picking_line))
                    if move_vals:
                        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing'),
                                                                              ('warehouse_id', '=',
                                                                               rec.warehouse_id.id)])
                        picking_id = self.env['stock.picking'].sudo().create({'partner_id': rec.partner_id.id,
                                                                              'scheduled_date': datetime.now(),
                                                                              'location_id': location_id.id,
                                                                              'location_dest_id': location_dest_id.id,
                                                                              'picking_type_id': picking_type.id,
                                                                              'origin': rec.name,
                                                                              'move_ids_without_package': move_vals
                                                                              })
                        picking_id.sudo().action_confirm()
                        picking_id.sudo().action_assign()
                rec.write({
                    'state': 'sale',
                    'date_order': fields.Datetime.now()
                })

            else:
                res = super(SaleOrder, self).action_confirm()
                return res
        return True


class saleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    location_id = fields.Many2one('stock.location', string="Location")
