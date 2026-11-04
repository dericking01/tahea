from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    tra_tax_code = fields.Selection([
        ('1', 'Standard 18%'),
        ('2', 'Special Rate'),
        ('3', 'Zero Rated'),
        ('4', 'Special Relief'),
        ('5', 'Exempted'),
    ], string='TRA Tax Code',
        help='Item tax code sent to TRA. Required for any tax other than a plain 18% or zero rated tax.')
