# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    product_location_id = fields.Many2one(
        'stock.location', string='Production Location', copy=False,
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
        help="Source location of the delivery orders created when this order is confirmed.",
    )
