import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .tra_config import TraEfdUncertainError, check_tra_access

_logger = logging.getLogger(__name__)

# WebSHOP builds TRA's XML from our text, and TRA rejects receipts containing these
TRA_TEXT_REPLACEMENTS = {'&': ' and ', '<': ' ', '>': ' ', '"': ' ', "'": ' '}


def _tra_clean_text(value):
    """Return text that is safe inside TRA's receipt XML, on a single line."""
    for char, replacement in TRA_TEXT_REPLACEMENTS.items():
        value = (value or '').replace(char, replacement)
    return re.sub(r'\s+', ' ', value).strip()


class AccountMove(models.Model):
    _inherit = 'account.move'

    tra_receipt_id = fields.Many2one(
        'tra.receipt',
        string='TRA Receipt',
        readonly=True,
        copy=False,
    )
    tra_receipt_status = fields.Selection(
        related='tra_receipt_id.status',
        string='TRA Receipt Status',
        readonly=True,
        store=True,
    )
    tra_receipt_number = fields.Char(
        related='tra_receipt_id.receipt_number',
        string='TRA Receipt No.',
        readonly=True,
        store=True,
    )
    tra_verification_code = fields.Char(
        related='tra_receipt_id.verification_code',
        string='TRA Verification Code',
        readonly=True,
        store=True,
    )
    tra_verify_link = fields.Char(
        related='tra_receipt_id.verify_link',
        string='TRA Verification Link',
        readonly=True,
    )
    tra_qr_code = fields.Binary(
        related='tra_receipt_id.qr_code_image',
        string='TRA QR Code',
        readonly=True,
    )
    tra_is_demo = fields.Boolean(
        related='tra_receipt_id.is_demo',
        string='TRA Demo Receipt',
        readonly=True,
    )
    tra_ack_state = fields.Selection(
        related='tra_receipt_id.tra_ack_state',
        string='TRA Acknowledgement',
        readonly=True,
        store=True,
    )
    tra_ack_message = fields.Char(
        related='tra_receipt_id.tra_ack_message',
        string='TRA Ack Message',
        readonly=True,
    )

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        moves = posted.filtered(lambda m: m.move_type == 'out_invoice'
                                and m.tra_receipt_status not in ('success', 'pending'))
        if moves and self.env['tra.efd.config'].sudo().search(
                [('active', '=', True)], limit=1).auto_generate_receipt:
            # Issue after commit: a fiscal receipt cannot be undone if the posting rolls back.
            move_ids, uid, context = moves.ids, self.env.uid, dict(self.env.context)
            registry = self.env.registry

            @self.env.cr.postcommit.add
            def _issue_receipts():
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    for move in env['account.move'].browse(move_ids):
                        try:
                            move._issue_tra_receipt()
                            cr.commit()
                        except Exception:
                            cr.rollback()
                            _logger.exception('Automatic TRA receipt failed for invoice %s', move.id)
        return posted

    def button_draft(self):
        self._check_tra_receipt_locked()
        return super().button_draft()

    def button_cancel(self):
        self._check_tra_receipt_locked()
        return super().button_cancel()

    def _check_tra_receipt_locked(self):
        for move in self:
            if move.tra_receipt_status in ('success', 'pending'):
                raise UserError(_(
                    'Invoice %s has a TRA receipt and can no longer be reset or cancelled.',
                    move.name))

    def _get_tra_invoice_ref(self):
        """The API cannot look up references containing '/', so send them with '-'."""
        self.ensure_one()
        return (self.name or str(self.id)).replace('/', '-')

    def _get_tra_mobile(self, partner):
        """Return the number as 0XXXXXXXXX, or '' when it cannot be normalised."""
        digits = re.sub(r'\D', '', partner.mobile or partner.phone or '')
        if digits.startswith('255'):
            digits = '0' + digits[3:]
        return digits if re.fullmatch(r'0\d{9}', digits) else ''

    def _get_tra_customer_data(self):
        """Extract customer TRA data from the invoice partner."""
        self.ensure_one()
        partner = self.partner_id
        mobile = self._get_tra_mobile(partner)
        # The TIN field comes first. Tax ID is a fallback for partners not yet updated, used
        # only when it is exactly 9 digits, since a VRN such as 40005434B is not a TIN.
        tin = partner._get_tra_tin() or re.sub(r'[\s-]', '', partner.vat or '')

        if re.fullmatch(r'\d{9}', tin):
            id_type, id_number = '1', tin
        else:
            id_type, id_number = '6', mobile

        return {
            'idtype': id_type,
            'idnumber': id_number,
            'mobile': mobile,
            'name': _tra_clean_text(partner.name),
        }

    def _get_tra_tax_code(self, line):
        """Return the TRA item tax code of an invoice line."""
        coded = line.tax_ids.filtered('tra_tax_code')
        if coded:
            return int(coded[0].tra_tax_code)
        for tax in line.tax_ids:
            if tax.amount == 18:
                return 1
            if tax.amount == 0:
                return 3
        raise UserError(_(
            'Cannot determine the TRA tax code for line "%s". '
            'Set a tax on the line and a TRA Tax Code on that tax.', line.name))

    def _get_tra_items(self):
        """Build TRA items list from invoice lines, in Tanzanian Shillings."""
        self.ensure_one()
        company = self.company_id
        if company.currency_id.name != 'TZS':
            raise UserError(_('TRA receipts require a company whose currency is TZS.'))
        date = self.invoice_date or fields.Date.context_today(self)

        items = []
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            net = self.currency_id._convert(line.price_subtotal, company.currency_id, company, date)
            tax_amount = self.currency_id._convert(
                line.price_total - line.price_subtotal, company.currency_id, company, date)
            net = round(net, 2)
            tax_amount = round(tax_amount, 2)

            items.append({
                'itemcode': _tra_clean_text(line.product_id.default_code) or 'ITEM',
                'itemdesc': _tra_clean_text(line.name or line.product_id.name) or 'Service',
                'itemqty': line.quantity,
                'net': net,
                'tax': tax_amount,
                'amount': round(net + tax_amount, 2),
                'discountamout': 0,
                'itemtaxcode': self._get_tra_tax_code(line),
            })
        if not items:
            raise UserError(_('Invoice %s has no product lines to send to TRA.', self.name))
        return items

    def _build_tra_payload(self):
        """Build the full generate receipt payload."""
        self.ensure_one()
        customer = self._get_tra_customer_data()
        items = self._get_tra_items()
        payment_type = 'INVOICE'
        if self.payment_state == 'paid':
            payment_type = 'CASH'

        return {
            'dbrecord': {
                'invoice_id': self._get_tra_invoice_ref(),
                'invoice_date': str(self.invoice_date or fields.Date.today()),
            },
            'customer': customer,
            'items': items,
            'payment': {
                'paymenttype': payment_type,
            },
        }

    def _issue_tra_receipt(self):
        """Send the invoice to TRA and link the resulting tra.receipt, whatever the outcome."""
        self.ensure_one()
        config = self.env['tra.efd.config'].get_active_config()
        Receipt = self.env['tra.receipt'].sudo()
        failure_vals = {
            'source_model': 'account.move',
            'source_id': self.id,
            'invoice_id_ref': self.name,
            'invoice_date': self.invoice_date,
            'account_move_id': self.id,
        }
        try:
            payload = self._build_tra_payload()
            _logger.info('Generating TRA receipt for Invoice %s', self.name)
            response = config._api_post('generatereceipt', payload)
        except TraEfdUncertainError as e:
            # TRA may have accepted it: block retries until the status has been checked.
            receipt = Receipt.create({**failure_vals, 'status': 'pending', 'error_message': str(e)})
        except UserError as e:
            receipt = Receipt.create({**failure_vals, 'status': 'failed', 'error_message': str(e)})
        else:
            receipt = Receipt.create_from_api_response(
                response_data=response,
                source_model='account.move',
                source_id=self.id,
                invoice_id_ref=self.name,
                invoice_date=self.invoice_date,
                account_move_id=self.id,
                payload=payload,
            )
        self.tra_receipt_id = receipt
        return receipt

    def _tra_notification(self, title, message, notification_type, next_action=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': notification_type != 'success',
                'next': next_action or {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _check_tra_receipt_allowed(self):
        self.ensure_one()
        check_tra_access(self.env)
        if self.move_type == 'out_refund':
            raise UserError(_('The TRA EFD API has no credit note support. '
                              'Credit notes cannot be sent as receipts.'))
        if self.move_type != 'out_invoice':
            raise UserError(_('TRA receipts can only be generated for customer invoices.'))
        if self.state != 'posted':
            raise UserError(_('Please confirm the invoice before generating a TRA receipt.'))
        if self.tra_receipt_status == 'success':
            raise UserError(_('Invoice %s already has TRA receipt #%s.',
                              self.name, self.tra_receipt_number))
        if self.tra_receipt_status == 'pending':
            raise UserError(_('The last attempt for invoice %s has an unknown result. '
                              'Use Check TRA Status first.', self.name))

    def action_generate_tra_receipt(self):
        """Show what will be sent to TRA, for the user to confirm before it is issued."""
        self._check_tra_receipt_allowed()
        return self.env['tra.receipt.confirm']._open_for_move(self)

    def _action_issue_tra_receipt(self, next_action=None):
        """Issue the receipt and return a notification describing the outcome."""
        self._check_tra_receipt_allowed()
        receipt = self._issue_tra_receipt()
        if receipt.status == 'success':
            return self._tra_notification(
                _('TRA Receipt Generated'),
                _('Receipt #%s generated successfully. Verification code: %s',
                  receipt.receipt_number, receipt.verification_code),
                'success', next_action)
        if receipt.status == 'pending':
            return self._tra_notification(
                _('TRA Receipt Status Unknown'),
                _('TRA may have accepted this invoice. Use Check TRA Status before trying again. %s',
                  receipt.error_message),
                'warning', next_action)
        return self._tra_notification(
            _('TRA Receipt Failed'), receipt.error_message, 'danger', next_action)

    def action_refresh_tra_ack(self):
        """Ask the API for TRA's acknowledgement of this invoice's receipt."""
        self.ensure_one()
        check_tra_access(self.env)
        self.tra_receipt_id._sync_tra_ack()
        if self.tra_ack_state == 'confirmed':
            return self._tra_notification(
                _('Confirmed by TRA'), _('TRA has accepted this receipt.'), 'success')
        if self.tra_ack_state == 'rejected':
            return self._tra_notification(
                _('TRA Receipt Needs Action'), self.tra_ack_message or '', 'danger')
        return self._tra_notification(
            _('Waiting for TRA'), _('TRA has not responded to this receipt yet.'), 'warning')

    def action_check_tra_receipt(self):
        """Resolve a pending receipt by asking the API whether the invoice was issued."""
        self.ensure_one()
        check_tra_access(self.env)
        receipt = self.tra_receipt_id
        if receipt.status != 'pending':
            raise UserError(_('This invoice has no receipt with an unknown result.'))

        config = self.env['tra.efd.config'].get_active_config()
        invoice_ref = self._get_tra_invoice_ref()
        data = config._api_get('invoiceno/%s' % invoice_ref)
        receipt_data = data.get('receiptData') if isinstance(data, dict) else None
        if (isinstance(receipt_data, dict) and receipt_data.get('receipt_number')
                and str(receipt_data.get('invoice_number')) == invoice_ref):
            receipt.sudo().write(receipt._prepare_vals_from_api(receipt_data))
            return self._tra_notification(
                _('TRA Receipt Found'),
                _('Receipt #%s was issued for this invoice.', receipt.receipt_number),
                'success')
        return self._tra_notification(
            _('TRA Receipt Not Found'),
            _('The API did not return a receipt for %s. Confirm on the WebSHOP portal, then an '
              'accounting manager can use Mark as Failed on the receipt to allow a retry.',
              invoice_ref),
            'warning')
