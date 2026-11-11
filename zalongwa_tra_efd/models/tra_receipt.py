import logging
import qrcode
import base64
from io import BytesIO
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

IDTYPE_MAP = {
    '1': 'TIN',
    '2': 'Driving License',
    '3': 'Voters Number',
    '4': 'Passport',
    '5': 'NIDA',
    '6': 'Telephone',
}


class TraReceipt(models.Model):
    _name = 'tra.receipt'
    _description = 'TRA EFD Receipt'
    _rec_name = 'receipt_number'
    _order = 'receipt_date desc, receipt_time desc'

    # Source reference
    source_model = fields.Char(string='Source Model')
    source_id = fields.Integer(string='Source ID')
    invoice_id_ref = fields.Char(string='Invoice Reference')
    invoice_date = fields.Date(string='Invoice Date')

    # TRA Receipt data
    receipt_number = fields.Char(string='Receipt Number', readonly=True)
    verification_code = fields.Char(string='Verification Code', readonly=True)
    receipt_date = fields.Date(string='Receipt Date', readonly=True)
    receipt_time = fields.Char(string='Receipt Time', readonly=True)
    znum = fields.Char(string='Z Number', readonly=True)
    vrn = fields.Char(string='VRN', readonly=True)
    verify_link = fields.Char(string='Verification Link', readonly=True)
    is_demo = fields.Boolean(string='Demo Receipt', readonly=True)

    # Amounts
    total_excl_tax = fields.Float(string='Total Excl. Tax', readonly=True, digits=(16, 2))
    total_tax = fields.Float(string='Total VAT', readonly=True, digits=(16, 2))
    total_incl_tax = fields.Float(string='Total Incl. Tax', readonly=True, digits=(16, 2))

    # Customer
    customer_id_type = fields.Char(string='Customer ID Type', readonly=True)
    customer_id_number = fields.Char(string='Customer ID Number', readonly=True)
    customer_name = fields.Char(string='Customer Name', readonly=True)
    customer_mobile = fields.Char(string='Customer Mobile', readonly=True)

    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    api_response_raw = fields.Text(string='API Response (Raw)', readonly=True)

    # TRA acknowledgement. Arrives after the receipt is issued, from invoiceno lookups.
    tra_ack_code = fields.Char(string='TRA Ack Code', readonly=True)
    tra_ack_message = fields.Char(string='TRA Ack Message', readonly=True)
    tra_ack_state = fields.Selection([
        ('waiting', 'Waiting for TRA'),
        ('confirmed', 'Confirmed by TRA'),
        ('rejected', 'Needs Action'),
    ], string='TRA Acknowledgement', compute='_compute_tra_ack_state', store=True)
    ack_last_check = fields.Datetime(string='Ack Last Checked', readonly=True)

    # QR Code
    qr_code_image = fields.Binary(string='QR Code', readonly=True, attachment=True)
    qr_code_url = fields.Char(string='QR Code URL', readonly=True)

    # Items
    item_ids = fields.One2many('tra.receipt.item', 'receipt_id', string='Items', readonly=True)

    # Related records
    account_move_id = fields.Many2one('account.move', string='Invoice', ondelete='set null')

    @api.depends('tra_ack_code')
    def _compute_tra_ack_state(self):
        for rec in self:
            if not rec.tra_ack_code:
                rec.tra_ack_state = 'waiting'
            elif rec.tra_ack_code == '0':
                rec.tra_ack_state = 'confirmed'
            else:
                rec.tra_ack_state = 'rejected'

    def _sync_tra_ack(self):
        """Fetch TRA's acknowledgement for these receipts and flag any rejection."""
        config = self.env['tra.efd.config'].get_active_config()
        for receipt in self.sudo().filtered('account_move_id'):
            move = receipt.account_move_id
            data = config._api_get('invoiceno/%s' % move._get_tra_invoice_ref())
            receipt_data = data.get('receiptData') if isinstance(data, dict) else None
            vals = {'ack_last_check': fields.Datetime.now()}
            if (isinstance(receipt_data, dict)
                    and str(receipt_data.get('receipt_number')) == receipt.receipt_number
                    and receipt_data.get('tra_ackcode') is not None):
                vals.update({
                    'tra_ack_code': str(receipt_data['tra_ackcode']),
                    'tra_ack_message': receipt_data.get('tra_ackmsg') or '',
                })
            was_rejected = receipt.tra_ack_state == 'rejected'
            receipt.write(vals)
            if receipt.tra_ack_state == 'rejected' and not was_rejected:
                move.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('TRA rejected receipt #%s', receipt.receipt_number),
                    note=_('TRA response %s: %s', receipt.tra_ack_code, receipt.tra_ack_message),
                    # Whoever issued the receipt is in Finance, unlike the salesperson
                    user_id=receipt.create_uid.id,
                )

    @api.model
    def _cron_sync_tra_ack(self, limit=50):
        """Recheck recent receipts that TRA has not confirmed, longest unchecked first."""
        receipts = self.search([
            ('status', '=', 'success'),
            ('tra_ack_state', 'in', ('waiting', 'rejected')),
            ('account_move_id', '!=', False),
            ('create_date', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=30)),
        ], order='ack_last_check asc nulls first', limit=limit)
        try:
            receipts._sync_tra_ack()
        except UserError as e:
            _logger.warning('TRA acknowledgement sync stopped: %s', e)

    def _generate_qr_code(self, url):
        """Generate a QR code image for the TRA verification URL."""
        if not url:
            return False, False
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_data = base64.b64encode(buffer.getvalue())
            return img_data, url
        except Exception as e:
            _logger.warning('QR code generation failed: %s', e)
            return False, url

    @api.model
    def _prepare_vals_from_api(self, response_data):
        """Map a generatereceipt or invoiceno receipt onto tra.receipt values."""
        # generatereceipt returns status. invoiceno has none, and a receipt number there means it
        # was issued even when TRA's ack code is an error, so it must never be sent again.
        if 'status' in response_data:
            is_success = response_data['status'] == 'success'
        else:
            is_success = bool(response_data.get('receipt_number'))
        verify_link = response_data.get('link', '') or response_data.get('verif_link', '')
        ack_code = response_data.get('tra_ackcode')

        qr_image, qr_url = self._generate_qr_code(verify_link)

        return {
            'receipt_number': str(response_data.get('receipt_number', '')),
            'verification_code': response_data.get('verificationcode', ''),
            'receipt_date': response_data.get('receipt_date'),
            'receipt_time': response_data.get('receipt_time', ''),
            'znum': response_data.get('znum', ''),
            'vrn': response_data.get('vrn', ''),
            'verify_link': verify_link,
            'is_demo': response_data.get('isdemo', 'no') == 'yes',
            'total_excl_tax': float(response_data.get('total_excl_of_tax', 0) or 0),
            'total_tax': float(response_data.get('total_tax', 0) or 0),
            'total_incl_tax': float(response_data.get('total_incl_of_tax', 0) or 0),
            'status': 'success' if is_success else 'failed',
            'error_message': False if is_success else (
                response_data.get('message') or str(response_data)),
            'api_response_raw': str(response_data),
            'qr_code_image': qr_image,
            'qr_code_url': qr_url,
            'tra_ack_code': str(ack_code) if ack_code is not None else False,
            'tra_ack_message': response_data.get('tra_ackmsg') or False,
        }

    @api.model
    def create_from_api_response(self, response_data, source_model=None, source_id=None,
                                  invoice_id_ref=None, invoice_date=None,
                                  account_move_id=None, payload=None):
        """Create a TRA receipt record from the API response dict and the payload sent."""
        vals = self._prepare_vals_from_api(response_data)
        vals.update({
            'source_model': source_model,
            'source_id': source_id,
            'invoice_id_ref': invoice_id_ref or response_data.get('invoice_id', ''),
            'invoice_date': invoice_date or response_data.get('invoice_date'),
            'account_move_id': account_move_id,
        })
        if payload:
            customer = payload.get('customer', {})
            vals.update({
                'customer_id_type': IDTYPE_MAP.get(customer.get('idtype'), ''),
                'customer_id_number': customer.get('idnumber', ''),
                'customer_name': customer.get('name', ''),
                'customer_mobile': customer.get('mobile', ''),
                'item_ids': [(0, 0, {
                    'itemcode': item.get('itemcode'),
                    'itemdesc': item.get('itemdesc'),
                    'itemqty': item.get('itemqty'),
                    'net': item.get('net'),
                    'tax': item.get('tax'),
                    'amount': item.get('amount'),
                    'discount': item.get('discountamout'),
                    'itemtaxcode': str(item.get('itemtaxcode')),
                }) for item in payload.get('items', [])],
            })
        return self.create(vals)

    def action_mark_failed(self):
        """Release the invoice for a new receipt once a person has checked this one."""
        self.filtered(lambda r: r.status == 'pending' or r.tra_ack_state == 'rejected').write(
            {'status': 'failed'})

    def action_view_qr(self):
        self.ensure_one()
        if not self.verify_link:
            raise UserError(_('No verification link available for this receipt.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.verify_link,
            'target': 'new',
        }

    def action_print_receipt(self):
        self.ensure_one()
        if self.status != 'success':
            raise UserError(_('Only successful receipts can be printed.'))
        return self.env.ref('zalongwa_tra_efd.action_report_tra_receipt').report_action(self)


class TraReceiptItem(models.Model):
    _name = 'tra.receipt.item'
    _description = 'TRA Receipt Line Item'

    receipt_id = fields.Many2one('tra.receipt', string='Receipt', ondelete='cascade', required=True)
    itemcode = fields.Char(string='Item Code')
    itemdesc = fields.Char(string='Description')
    itemqty = fields.Float(string='Quantity', digits=(16, 3))
    net = fields.Float(string='Net Amount', digits=(16, 2))
    tax = fields.Float(string='Tax Amount', digits=(16, 2))
    amount = fields.Float(string='Total Amount', digits=(16, 2))
    discount = fields.Float(string='Discount', digits=(16, 2))
    itemtaxcode = fields.Selection([
        ('1', 'Standard 18%'),
        ('2', 'Special Rate'),
        ('3', 'Zero Rated'),
        ('4', 'Special Relief'),
        ('5', 'Exempted'),
    ], string='Tax Code')
