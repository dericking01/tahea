import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    tra_tin = fields.Char(
        string='TIN',
        help='Taxpayer Identification Number, 9 digits (e.g. 150-145-147). Sent to TRA on receipts.'
    )
    tra_vrn = fields.Char(
        string='VRN',
        help='VAT Registration Number (e.g. 40-041972-Q). Kept for reference, the TRA API does not accept it.'
    )

    @api.model
    def _commercial_fields(self):
        # Contacts share the TIN and VRN of their company, like the Tax ID
        return super()._commercial_fields() + ['tra_tin', 'tra_vrn']

    def _get_tra_tin(self):
        """Return the TIN as 9 digits, or '' when none is set."""
        return re.sub(r'[\s-]', '', self.commercial_partner_id.tra_tin or '')

    @api.constrains('tra_tin')
    def _check_tra_tin(self):
        for partner in self:
            if partner.tra_tin and not re.fullmatch(r'\d{9}', partner._get_tra_tin()):
                raise ValidationError(_('TIN must be 9 digits, for example 150-145-147.'))

    @api.constrains('tra_vrn')
    def _check_tra_vrn(self):
        for partner in self:
            vrn = re.sub(r'[\s-]', '', partner.tra_vrn or '')
            if vrn and not re.fullmatch(r'\d{8}[A-Za-z]', vrn):
                raise ValidationError(_('VRN must be 8 digits and a letter, for example 40-041972-Q.'))
