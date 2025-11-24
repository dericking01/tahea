from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PaymentRegisterValidation(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.constrains('amount','payment_difference')
    def validate_payment_amount(self):
        for payment in self:
            if payment.payment_type == 'outbound' and payment.payment_difference < 0.00:
                raise UserError('Paying amount is greater than the amount to be paid. You cannot proceed this payment.')