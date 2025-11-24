# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class SrCreateRequestForQuotation(models.TransientModel):
    _name = "sr.create.request.for.quotation"
    _description = "Create Request For Quotation"

    partner_id = fields.Many2one('res.partner', string="Partner")

    def create_request_for_quotation(self):
        pur_id = self.env['purchase.order'].create({'partner_id': self.partner_id.id})
        for product in self._context.get('active_ids'):
            line = self.env['product.product'].browse(product)
            self.env['purchase.order.line'].create({
                'product_id': product,
                'order_id': pur_id.id,
                'name': line.name,
                'product_qty': 1,
                'price_unit': line.standard_price,
                'date_planned': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'product_uom': line.uom_po_id.id or line.uom_id.id
            })

        action = self.env.ref('purchase.purchase_rfq').read()[0]
        action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
        action['res_id'] = pur_id.ids[0]
        return action
