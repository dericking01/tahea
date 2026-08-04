# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    move_waste_ids = fields.One2many(
        'stock.move', compute='_compute_move_waste_ids', inverse='_set_move_waste_ids')

    def _compute_move_byproduct_ids(self):
        super()._compute_move_byproduct_ids()
        for order in self:
            order.move_byproduct_ids = order.move_byproduct_ids.filtered(lambda m: not m.is_waste)

    def _set_move_byproduct_ids(self):
        for order in self:
            move_finished_ids = order.move_finished_ids.filtered(lambda m: m.product_id == order.product_id or m.is_waste)
            order.move_finished_ids = move_finished_ids | order.move_byproduct_ids

    def _compute_move_waste_ids(self):
        for order in self:
            order.move_waste_ids = order.move_finished_ids.filtered(
                lambda m: m.product_id != order.product_id and m.is_waste)

    def _set_move_waste_ids(self):
        for order in self:
            move_finished_ids = order.move_finished_ids.filtered(lambda m: m.product_id == order.product_id or not m.is_waste)
            order.move_finished_ids = move_finished_ids | order.move_waste_ids
