from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quotation_reference = fields.Char(string='Reference')

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['quotation_reference'] = self.quotation_reference
        return vals


class AccountMove(models.Model):
    _inherit = 'account.move'

    quotation_reference = fields.Char(string='Reference', copy=False)
