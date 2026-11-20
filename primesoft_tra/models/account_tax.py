from odoo import models, fields, _
from odoo.exceptions import UserError

TRA_TAX_CODES = [
    ('1', 'Standard 18%'),
    ('2', 'Special Rate'),
    ('3', 'Zero Rated'),
    ('4', 'Special Relief'),
    ('5', 'Exempted'),
]


class AccountTax(models.Model):
    _inherit = 'account.tax'

    tra_tax_code = fields.Selection(
        TRA_TAX_CODES, string='TRA Tax Code',
        help='Item tax code sent to TRA. Required for any tax other than a plain 18% or zero rated tax.')

    def _get_tra_item_tax_code(self, line_label):
        """Return the TRA item tax code for a line carrying these taxes."""
        coded = self.filtered('tra_tax_code')
        if coded:
            return int(coded[0].tra_tax_code)
        for tax in self:
            if tax.amount == 18:
                return 1
            if tax.amount == 0:
                return 3
        if not self:
            default = self.env['tra.efd.config'].sudo().search(
                [('active', '=', True)], limit=1).default_tax_code
            if default:
                return int(default)
        raise UserError(_(
            'Cannot determine the TRA tax code for line "%s". '
            'Set a tax on the line and a TRA Tax Code on that tax.', line_label))
