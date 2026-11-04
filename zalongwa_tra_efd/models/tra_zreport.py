import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TraZReport(models.Model):
    _name = 'tra.zreport'
    _description = 'TRA EFD Z-Report'
    _rec_name = 'report_number'
    _order = 'report_date desc'

    report_number = fields.Char(string='Report Number', readonly=True)
    report_date = fields.Date(string='Report Date', readonly=True)
    report_time = fields.Char(string='Report Time', readonly=True)
    subtotal = fields.Float(string='Subtotal', readonly=True, digits=(16, 2))
    discount = fields.Float(string='Discount', readonly=True, digits=(16, 2))
    total = fields.Float(string='Total', readonly=True, digits=(16, 2))
    vat = fields.Float(string='VAT', readonly=True, digits=(16, 2))
    total_gross = fields.Float(string='Total Gross Cumulative', readonly=True, digits=(16, 2))
    ack_code = fields.Char(string='ACK Code', readonly=True)
    ack_msg = fields.Char(string='ACK Message', readonly=True)
    xml_payload = fields.Text(string='XML Payload', readonly=True)

    @api.model
    def action_sync_zreports(self):
        """Pull all Z-Reports from API and sync locally."""
        config = self.env['tra.efd.config'].get_active_config()
        data = config._api_get('zreport')
        # API errors can arrive as HTTP 200, so a missing key is a failure, not an empty list
        if 'zreport' not in data:
            raise UserError(_('Could not read Z-Reports from TRA: %s') % data)
        reports = data['zreport']
        synced = 0
        ZReport = self.sudo()
        for r in reports:
            existing = ZReport.search([('report_number', '=', r.get('report_number'))], limit=1)
            vals = {
                'report_number': r.get('report_number'),
                'report_date': r.get('report_date'),
                'report_time': r.get('report_time'),
                'subtotal': float(r.get('subtotal') or 0),
                'discount': float(r.get('discount') or 0),
                'total': float(r.get('total') or 0),
                'vat': float(r.get('vat') or 0),
                'total_gross': float(r.get('total_gross') or 0),
                'ack_code': r.get('ACKCODE', ''),
                'ack_msg': r.get('ACKMSG', ''),
                'xml_payload': r.get('XmlPayLoad', ''),
            }
            if existing:
                existing.write(vals)
            else:
                ZReport.create(vals)
                synced += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Z-Reports Synced'),
                'message': _('%d new Z-Reports imported from TRA.') % synced,
                'type': 'success',
                'sticky': False,
            },
        }
