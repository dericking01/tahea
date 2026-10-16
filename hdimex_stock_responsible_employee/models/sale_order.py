# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    product_location_id = fields.Many2one(
        'stock.location', string='Production Location', copy=False,
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
        help="Source location of the delivery orders created when this order is confirmed.",
    )

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Show 'Production Location' once: when another view already
        displays it, drop the placement added by this module."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            nodes = arch.xpath("//field[@name='product_location_id']")
            if len(nodes) > 1:
                for node in nodes:
                    if 'hdimex_product_location' in (node.get('class') or '').split():
                        node.getparent().remove(node)
        return arch, view
