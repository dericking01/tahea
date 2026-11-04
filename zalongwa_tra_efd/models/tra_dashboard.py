from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TraReceipt(models.Model):
    _inherit = 'tra.receipt'

    @api.model
    def get_dashboard_data(self):
        """Return everything the TRA EFD dashboard shows, except the WebSHOP totals."""
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        trend_start = today - timedelta(days=13)
        config = self.env['tra.efd.config'].sudo().search([('active', '=', True)], limit=1)
        go_live = config.go_live_date or today

        # Demo receipts are not fiscal records, so they stay out of every total
        live = [('status', '=', 'success'), ('is_demo', '=', False)]
        month_receipts = self.search(live + [('receipt_date', '>=', month_start)])
        trend_receipts = self.search(live + [('receipt_date', '>=', trend_start)])
        today_receipts = month_receipts.filtered(lambda r: r.receipt_date == today)

        rejected = [('status', '=', 'success'), ('tra_ack_state', '=', 'rejected')]
        waiting = [('status', '=', 'success'), ('tra_ack_state', '=', 'waiting')]
        pending = [('status', '=', 'pending')]
        missing = [
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', go_live),
            '|', ('tra_receipt_id', '=', False), ('tra_receipt_status', '=', 'failed'),
        ]

        def card(label, value, hint, tone, res_model, domain):
            return {
                'label': label, 'value': value, 'hint': hint, 'tone': tone,
                'res_model': res_model, 'domain': domain,
            }

        attention = [
            card(_('Rejected by TRA'), self.search_count(rejected),
                 _('Issued, but TRA returned an error'), 'danger', 'tra.receipt', rejected),
            card(_('Result Unknown'), self.search_count(pending),
                 _('No answer from the API, retry is blocked'), 'warning', 'tra.receipt', pending),
            card(_('Invoices Without Receipt'), self.env['account.move'].search_count(missing),
                 _('Confirmed since go-live, no valid receipt'), 'warning', 'account.move', missing),
            card(_('Waiting for TRA'), self.search_count(waiting),
                 _('Issued, TRA response not received yet'), 'info', 'tra.receipt', waiting),
        ]

        totals = [
            {'label': _('Receipts Today'), 'value': len(today_receipts), 'money': False},
            {'label': _('Sales Today'), 'value': sum(today_receipts.mapped('total_incl_tax')), 'money': True},
            {'label': _('Sales This Month'), 'value': sum(month_receipts.mapped('total_incl_tax')), 'money': True},
            {'label': _('VAT This Month'), 'value': sum(month_receipts.mapped('total_tax')), 'money': True},
        ]

        trend = []
        for offset in range(14):
            day = trend_start + timedelta(days=offset)
            day_receipts = trend_receipts.filtered(lambda r: r.receipt_date == day)
            trend.append({
                'date': str(day),
                'label': day.strftime('%d %b'),
                'count': len(day_receipts),
                'amount': sum(day_receipts.mapped('total_incl_tax')),
            })
        peak = max(day['amount'] for day in trend) or 1
        for day in trend:
            day['percent'] = round(day['amount'] * 100 / peak)

        item_model = self.env['tra.receipt.item']
        code_labels = dict(item_model._fields['itemtaxcode'].selection)
        by_code = {}
        for item in item_model.search([('receipt_id', 'in', month_receipts.ids)]):
            row = by_code.setdefault(item.itemtaxcode, {
                'label': code_labels.get(item.itemtaxcode, _('Unknown')), 'net': 0, 'tax': 0, 'amount': 0})
            row['net'] += item.net
            row['tax'] += item.tax
            row['amount'] += item.amount

        issues = self.search(
            ['|', ('status', '=', 'pending'), '&', ('status', '=', 'success'), ('tra_ack_state', '=', 'rejected')],
            order='create_date desc', limit=10)

        zreport = self.env['tra.zreport'].search([], order='report_date desc', limit=1)
        last_connection = config.last_connection and fields.Datetime.context_timestamp(
            self, config.last_connection).strftime('%Y-%m-%d %H:%M')

        return {
            'attention': attention,
            'totals': totals,
            'trend': trend,
            'tax_codes': list(by_code.values()),
            'issues': [{
                'id': issue.id,
                'invoice': issue.invoice_id_ref or '',
                'receipt_number': issue.receipt_number or '',
                'problem': _('Result unknown') if issue.status == 'pending' else _('Rejected by TRA'),
                'message': issue.error_message if issue.status == 'pending' else issue.tra_ack_message,
            } for issue in issues],
            'demo_count': self.search_count([('status', '=', 'success'), ('is_demo', '=', True)]),
            'connection': {
                'configured': bool(config),
                'status': config.connection_status or 'not_tested',
                'last_connection': last_connection or '',
                'vrn': config.company_vrn or '',
                'tin': config.company_tin or '',
                'serial': config.company_serial or '',
                'tax_office': config.tax_office or '',
                'auto': config.auto_generate_receipt,
                'go_live': str(go_live),
            },
            'zreport': {
                'number': zreport.report_number or '',
                'date': str(zreport.report_date or ''),
                'total': zreport.total,
                'vat': zreport.vat,
            },
        }

    @api.model
    def get_dashboard_api_totals(self):
        """Live totals from WebSHOP, loaded separately so a slow API cannot block the dashboard."""
        try:
            data = self.env['tra.efd.config'].get_active_config()._api_get('dashboard')
        except UserError as e:
            return {'error': str(e)}
        dashboard = data.get('dashboard') if isinstance(data, dict) else None
        if not isinstance(dashboard, dict):
            return {'error': _('WebSHOP returned an unexpected response.')}
        return {
            'count': int(dashboard.get('total_rct') or 0),
            'amount': float(dashboard.get('total_amount') or 0),
            'month_amount': float(dashboard.get('total_month_amount') or 0),
        }

    @api.model
    def action_dashboard_sync(self):
        """Refresh TRA acknowledgements and Z-Reports from the dashboard."""
        self._cron_sync_tra_ack()
        try:
            self.env['tra.zreport'].action_sync_zreports()
        except UserError as e:
            return {'error': str(e)}
        return {}
