from odoo import models, fields

# Payment types accepted by the WebSHOP API
TRA_PAYMENT_TYPES = [
    ('CASH', 'Cash'),
    ('CHEQUE', 'Cheque'),
    ('CCARD', 'Credit card'),
    ('EMONEY', 'E-money'),
    ('INVOICE', 'Invoice'),
]


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    tra_payment_type = fields.Selection(
        TRA_PAYMENT_TYPES,
        string='TRA Payment Type',
        help='Payment type sent to TRA. When empty, it is guessed from the method type and name.',
    )

    def _get_tra_payment_type(self):
        self.ensure_one()
        if self.tra_payment_type:
            return self.tra_payment_type
        if self.type == 'cash':
            return 'CASH'
        if self.type == 'pay_later':
            return 'INVOICE'
        name = (self.name or '').upper()
        if 'CHEQUE' in name or 'CHECK' in name:
            return 'CHEQUE'
        if any(word in name for word in ('CARD', 'VISA', 'MASTERCARD')):
            return 'CCARD'
        if any(word in name for word in (
                'MOBILE', 'MPESA', 'M-PESA', 'TIGO', 'AIRTEL', 'EMONEY', 'HALOPESA', 'MIXX')):
            return 'EMONEY'
        if 'INVOICE' in name or 'CREDIT' in name:
            return 'INVOICE'
        return 'CASH'
