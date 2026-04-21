from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        # Reuse Studio-managed field and propagate from quotation to invoice.
        if 'x_studio_reference' in self._fields:
            vals['x_studio_reference'] = self.x_studio_reference
        return vals
