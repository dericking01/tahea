# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Use built-in categ_id as the main category
    subcategory_id = fields.Many2one(
        'product.category',
        string='Subcategory',
        domain="[('parent_id', '=', categ_id)]"
    )
