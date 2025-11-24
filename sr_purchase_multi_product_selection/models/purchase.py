# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

from odoo import api, fields, models
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class SrMultiProductpurchase(models.TransientModel):
    _name = 'sr.multi.product.purchase'
    _description = 'Multi Product Purchase'

    product_ids = fields.Many2many('product.product', string="Product")

    def add_product(self):
        for line in self.product_ids:
            self.env['purchase.order.line'].create({
                'product_id': line.id,
                'name':line.name,
                'product_qty':1,
                'price_unit':line.standard_price,
                'order_id': self._context.get('active_id'),
                'date_planned':datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'product_uom' : line.uom_po_id.id or line.uom_id.id
            })
        return
