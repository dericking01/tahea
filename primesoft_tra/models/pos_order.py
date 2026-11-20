import logging
import re
from datetime import timedelta

import pytz
from psycopg2.errors import LockNotAvailable

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools import mute_logger

from .account_move import _tra_clean_text
from .tra_config import TraEfdUncertainError, check_tra_access

_logger = logging.getLogger(__name__)

# Orders older than this are not retried automatically by the cron.
CRON_RETRY_DAYS = 2
TRA_TIMEZONE = pytz.timezone('Africa/Dar_es_Salaam')
PAID_STATES = ('paid', 'done', 'invoiced')
# The only TRA values the POS screen may set. Everything else is decided by the server.
CASHIER_FIELDS = ('tra_receipt_type', 'tra_customer_tin')


def normalize_tin(value):
    """Return the 9-digit TIN contained in value, or '' when it is not a valid TIN."""
    digits = re.sub(r'\D', '', value or '')
    return digits if len(digits) == 9 else ''


class PosOrder(models.Model):
    _inherit = 'pos.order'

    tra_receipt_type = fields.Selection(
        selection=[('tra', 'TRA Fiscal Receipt'), ('default', 'Standard Receipt')],
        string='Receipt Type',
        default='tra',
        copy=False,
    )
    tra_customer_tin = fields.Char(string='Customer TIN', copy=False)
    tra_receipt_id = fields.Many2one('tra.receipt', string='TRA Receipt', readonly=True, copy=False)
    tra_receipt_status = fields.Selection(
        related='tra_receipt_id.status', string='TRA Receipt Status', store=True)
    tra_receipt_number = fields.Char(
        related='tra_receipt_id.receipt_number', string='TRA Receipt No.', store=True)
    tra_verification_code = fields.Char(
        related='tra_receipt_id.verification_code', string='TRA Verification Code', store=True)
    tra_ack_state = fields.Selection(
        related='tra_receipt_id.tra_ack_state', string='TRA Acknowledgement', store=True)
    tra_znum = fields.Char(related='tra_receipt_id.znum', string='TRA Z-Number')
    tra_receipt_date = fields.Date(related='tra_receipt_id.receipt_date', string='TRA Receipt Date')
    tra_receipt_time = fields.Char(related='tra_receipt_id.receipt_time', string='TRA Receipt Time')
    tra_verify_link = fields.Char(related='tra_receipt_id.verify_link', string='TRA Verification Link')
    tra_error = fields.Text(related='tra_receipt_id.error_message', string='TRA Error')

    # ── POS sync ───────────────────────────────────────────────────────────────
    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        # An empty list means "all fields"; only extend an explicit list.
        if fields_list:
            fields_list += list(CASHIER_FIELDS)
        return fields_list

    @api.model
    def _process_order(self, order, *args, **kwargs):
        existing = args[0] if args else kwargs.get('existing_order')
        locked = bool(existing) and existing.tra_receipt_status in ('success', 'pending')
        # The POS sends back every field it loaded. A stale copy must never overwrite the
        # receipt link, and the cashier's choices are frozen once a receipt exists.
        order = {
            key: value for key, value in order.items()
            if not key.startswith('tra_') or (key in CASHIER_FIELDS and not locked)
        }
        if not locked:
            order['tra_receipt_type'] = order.get('tra_receipt_type') or 'default'
            order['tra_customer_tin'] = normalize_tin(order.get('tra_customer_tin'))

        order_id = super()._process_order(order, *args, **kwargs)
        if not order_id:
            return order_id

        pos_order = self.browse(order_id)
        if pos_order.state in PAID_STATES and not pos_order.tra_receipt_id:
            if pos_order.tra_receipt_type == 'tra' and pos_order._is_tra_refund():
                # The API has no credit note: a refund prints the standard receipt.
                pos_order.sudo().tra_receipt_type = 'default'
            elif pos_order._should_submit_to_tra():
                pos_order._schedule_tra_submission()
        return order_id

    def _is_tra_refund(self):
        self.ensure_one()
        return self.currency_id.compare_amounts(self.amount_total, 0) <= 0

    def _should_submit_to_tra(self):
        self.ensure_one()
        if self.tra_receipt_status in ('success', 'pending'):
            return False
        if self.tra_receipt_type != 'tra' or self._is_tra_refund():
            return False
        if not self.session_id.config_id.tra_receipt_enabled:
            return False
        config = self.env['tra.efd.config'].sudo().search([('active', '=', True)], limit=1)
        if not config.use_on_pos:
            _logger.info('TRA EFD: order %s skipped, Point of Sale is off in the TRA settings.', self.name)
            return False
        return True

    def _schedule_tra_submission(self):
        """
        Submit to TRA only after the POS sync transaction is committed, so a rollback can
        never leave a fiscal receipt at TRA that Odoo does not know about. The hook still
        runs before the sync response is returned to the POS.
        """
        order_ids = self.ids
        dbname = self.env.cr.dbname

        @self.env.cr.postcommit.add
        def _submit_after_commit():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    for order in env['pos.order'].browse(order_ids):
                        order._issue_tra_receipt()
                        cr.commit()
            except Exception:
                _logger.exception('TRA EFD: post-commit submission failed for POS orders %s', order_ids)

    # ── Payload ────────────────────────────────────────────────────────────────
    def _get_tra_invoice_ref(self):
        """The API looks receipts up by this reference, so keep it to letters, digits and '-'."""
        self.ensure_one()
        return re.sub(r'[^A-Za-z0-9]+', '-', self.name or '').strip('-') or 'POS-%s' % self.id

    def _get_tra_date(self):
        self.ensure_one()
        return pytz.utc.localize(self.date_order).astimezone(TRA_TIMEZONE).date()

    def _get_tra_customer_data(self):
        """The TIN typed by the cashier wins, then the customer's TIN, then their telephone."""
        self.ensure_one()
        partner = self.partner_id
        mobile = self.env['account.move']._get_tra_mobile(partner) if partner else ''
        tin = normalize_tin(self.tra_customer_tin)
        if not tin and partner:
            tin = normalize_tin(partner._get_tra_tin() or partner.vat)
        return {
            'idtype': '1' if tin else '6',
            'idnumber': tin or mobile,
            'mobile': mobile,
            'name': _tra_clean_text(partner.name) if partner else 'Walk-in Customer',
        }

    def _get_tra_items(self):
        """Build the TRA items from the order lines, in Tanzanian Shillings."""
        self.ensure_one()
        company = self.company_id
        if company.currency_id.name != 'TZS':
            raise UserError(_('TRA receipts require a company whose currency is TZS.'))
        currency = self.currency_id
        date = self._get_tra_date()

        def to_tzs(amount):
            if currency == company.currency_id:
                return amount
            return currency._convert(amount, company.currency_id, company, date)

        sold, reductions = [], []
        for line in self.lines:
            net = to_tzs(line.price_subtotal)
            total = to_tzs(line.price_subtotal_incl)
            entry = {'line': line, 'net': net, 'tax': total - net,
                     'taxes': line.tax_ids_after_fiscal_position}
            if total > 0:
                sold.append(entry)
            elif total < 0:
                reductions.append(entry)
        if not sold:
            raise UserError(_('POS order %s has no lines to send to TRA.', self.name))

        # TRA has no negative items: spread discount and reward lines over the items they
        # reduce, on lines with the same taxes when there are any.
        for reduction in reductions:
            targets = [e for e in sold if e['taxes'] == reduction['taxes']] or sold
            base = sum(e['net'] + e['tax'] for e in targets)
            for entry in targets:
                share = (entry['net'] + entry['tax']) / base
                entry['net'] += reduction['net'] * share
                entry['tax'] += reduction['tax'] * share

        items = []
        for entry in sold:
            line = entry['line']
            net, tax = round(entry['net'], 2), round(entry['tax'], 2)
            if net + tax <= 0:
                raise UserError(_(
                    'Discounts on POS order %s exceed the items they apply to, so it cannot be '
                    'sent to TRA.', self.name))
            description = _tra_clean_text(line.full_product_name or line.product_id.name) or 'Item'
            items.append({
                'itemcode': _tra_clean_text(line.product_id.default_code) or 'ITEM',
                'itemdesc': description,
                'itemqty': line.qty,
                'net': net,
                'tax': tax,
                'amount': round(net + tax, 2),
                'discountamout': 0,
                'itemtaxcode': entry['taxes']._get_tra_item_tax_code(description),
            })
        return items

    def _get_tra_payment_type(self):
        """The payment type of the largest payment."""
        self.ensure_one()
        payments = self.payment_ids.filtered(lambda p: not p.is_change)
        if not payments:
            return 'CASH'
        return max(payments, key=lambda p: abs(p.amount)).payment_method_id._get_tra_payment_type()

    def _build_tra_payload(self):
        self.ensure_one()
        return {
            'dbrecord': {
                'invoice_id': self._get_tra_invoice_ref(),
                'invoice_date': str(self._get_tra_date()),
            },
            'customer': self._get_tra_customer_data(),
            'items': self._get_tra_items(),
            'payment': {'paymenttype': self._get_tra_payment_type()},
        }

    # ── Issuing ────────────────────────────────────────────────────────────────
    def _lock_for_tra(self):
        """Lock the order row so two workers never submit the same order."""
        try:
            with mute_logger('odoo.sql_db'), self.env.cr.savepoint():
                self.env.cr.execute(
                    'SELECT id FROM pos_order WHERE id = %s FOR UPDATE NOWAIT', [self.id])
        except LockNotAvailable:
            return False
        self.invalidate_recordset(['tra_receipt_id', 'tra_receipt_status'])
        return True

    def _link_tra_receipt_to_invoice(self):
        """The invoice of a POS order shows the order's receipt and is never sent again."""
        receipt = self.tra_receipt_id
        if self.account_move and receipt.status in ('success', 'pending'):
            self.account_move.sudo().tra_receipt_id = receipt

    def _issue_tra_receipt(self):
        """Send the order to TRA and link the resulting tra.receipt, whatever the outcome."""
        self.ensure_one()
        if not self._lock_for_tra() or self.tra_receipt_status in ('success', 'pending'):
            return self.tra_receipt_id

        Receipt = self.env['tra.receipt'].sudo()
        source_vals = {
            'source_model': 'pos.order',
            'source_id': self.id,
            'invoice_id_ref': self.name,
            'invoice_date': self._get_tra_date(),
            'pos_order_id': self.id,
        }
        try:
            config = self.env['tra.efd.config'].get_active_config()
            payload = self._build_tra_payload()
            _logger.info('Generating TRA receipt for POS order %s', self.name)
            response = config._api_post('generatereceipt', payload)
        except TraEfdUncertainError as e:
            # TRA may have accepted it: block retries until the status has been checked.
            receipt = Receipt.create({**source_vals, 'status': 'pending', 'error_message': str(e)})
        except UserError as e:
            receipt = Receipt.create({**source_vals, 'status': 'failed', 'error_message': str(e)})
        else:
            # Logged in full so the receipt can be recovered if the write below fails.
            _logger.info('TRA EFD: POS order %s answered %s', self.name, response)
            receipt = Receipt.create_from_api_response(
                response_data=response, payload=payload, **source_vals)

        # A retry replaces the failed attempt, so the cron does not pile up records
        previous = self.sudo().tra_receipt_id
        self.sudo().tra_receipt_id = receipt
        previous.unlink()
        self._link_tra_receipt_to_invoice()
        return receipt

    def _resolve_pending_tra_receipt(self):
        """Ask the API whether a timed-out order was issued. Returns True when it was."""
        self.ensure_one()
        receipt = self.sudo().tra_receipt_id
        api_ref = self._get_tra_invoice_ref()
        data = self.env['tra.efd.config'].get_active_config()._api_get('invoiceno/%s' % api_ref)
        receipt_data = data.get('receiptData') if isinstance(data, dict) else None
        if not (isinstance(receipt_data, dict) and receipt_data.get('receipt_number')
                and str(receipt_data.get('invoice_number')) == api_ref):
            return False
        receipt.write(receipt._prepare_vals_from_api(receipt_data))
        self._link_tra_receipt_to_invoice()
        return True

    @api.model
    def _cron_retry_tra_submissions(self):
        """Retry recent orders that failed, and look up the ones whose result is unknown."""
        orders = self.search([
            ('tra_receipt_type', '=', 'tra'),
            ('state', 'in', PAID_STATES),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=CRON_RETRY_DAYS)),
            '|', ('tra_receipt_id', '=', False), ('tra_receipt_status', 'in', ('failed', 'pending')),
        ], limit=100, order='id desc')
        for order in orders:
            try:
                if order.tra_receipt_status == 'pending':
                    order._resolve_pending_tra_receipt()
                elif order._should_submit_to_tra():
                    order._issue_tra_receipt()
                self.env.cr.commit()
            except Exception:
                self.env.cr.rollback()
                _logger.exception('TRA EFD: retry failed for POS order %s', order.id)

    # ── Backend buttons ────────────────────────────────────────────────────────
    def _tra_notification(self, message, notification_type):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': notification_type,
                'sticky': notification_type != 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_retry_tra_submission(self):
        """Send paid orders that have no valid receipt to TRA."""
        check_tra_access(self.env)
        if not self.env['tra.efd.config'].get_active_config().use_on_pos:
            raise UserError(_('TRA receipts on Point of Sale are switched off in the TRA EFD settings.'))
        done, failed = 0, []
        for order in self:
            if order.tra_receipt_status in ('success', 'pending') or order.state not in PAID_STATES:
                continue
            if order._is_tra_refund():
                raise UserError(_('The TRA EFD API has no credit note support. '
                                  'Refund %s cannot be sent as a receipt.', order.name))
            order.sudo().tra_receipt_type = 'tra'
            if order._issue_tra_receipt().status == 'success':
                done += 1
            else:
                failed.append(order.name)

        message = _('%s order(s) sent to TRA.', done)
        if failed:
            message += ' ' + _('Not issued: %s. See the TRA EFD tab of the order.', ', '.join(failed))
        return self._tra_notification(message, 'warning' if failed else 'success')

    def action_check_tra_receipt(self):
        """Resolve a receipt whose result is unknown by asking the API for it."""
        self.ensure_one()
        check_tra_access(self.env)
        if self.tra_receipt_status != 'pending':
            raise UserError(_('This order has no receipt with an unknown result.'))
        if self._resolve_pending_tra_receipt():
            return self._tra_notification(
                _('Receipt #%s was issued for this order.', self.tra_receipt_number), 'success')
        return self._tra_notification(
            _('The API did not return a receipt for %s. Confirm on the WebSHOP portal, then a '
              'manager can use Mark as Failed on the receipt to allow a retry.',
              self._get_tra_invoice_ref()),
            'warning')

    # ── Data for the printed POS receipt ───────────────────────────────────────
    @api.model
    def get_tra_receipt_header(self):
        """Seller details for a receipt printed before the order reached the server."""
        config = self.env['tra.efd.config'].sudo().search([('active', '=', True)], limit=1)
        return config._get_receipt_header_values(self.env.company)

    def get_tra_receipt_data(self):
        self.ensure_one()
        receipt = self.sudo().tra_receipt_id
        issued = receipt.status == 'success'
        qr_image = ''
        if issued and receipt.qr_code_image:
            qr_image = 'data:image/png;base64,' + receipt.qr_code_image.decode()
        config = self.env['tra.efd.config'].sudo().search([('active', '=', True)], limit=1)
        return {
            'tra_receipt_type': self.tra_receipt_type,
            'tra_customer_tin': self.tra_customer_tin or '',
            'tra_submitted': issued,
            'tra_is_demo': issued and receipt.is_demo,
            'tra_receipt_number': receipt.receipt_number if issued else '',
            'tra_z_number': receipt.znum if issued else '',
            'tra_receipt_datetime': (
                '%s %s' % (receipt.receipt_date, receipt.receipt_time) if issued else ''),
            'tra_verification_code': receipt.verification_code if issued else '',
            'tra_qr_url': receipt.verify_link if issued else '',
            'tra_qr_image': qr_image,
            'tra_error': '' if issued else (receipt.error_message or ''),
            **config._get_receipt_header_values(self.company_id),
        }
