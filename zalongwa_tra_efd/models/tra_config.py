import requests
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TraEfdUncertainError(UserError):
    """The request may have reached TRA, but no usable response came back."""


class TraEfdConfig(models.Model):
    _name = 'tra.efd.config'
    _description = 'TRA EFD Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True, default='TRA EFD Config')
    active = fields.Boolean(default=True)

    # API Credentials
    api_base_url = fields.Char(
        string='API Base URL',
        required=True,
        default='https://webshop.co.tz/api/public/index.php/api/v1',
        help='Zalongwa WebSHOP VEFD API base URL'
    )
    client_id = fields.Char(string='Client ID', required=True)
    client_secret = fields.Char(string='Client Secret', required=True)

    # Token storage
    access_token = fields.Char(string='Access Token', readonly=True)
    token_expiry = fields.Datetime(string='Token Expiry', readonly=True)
    token_user_name = fields.Char(string='Token User', readonly=True)
    token_email = fields.Char(string='Token Email', readonly=True)

    # Company Info from API
    company_vrn = fields.Char(string='VRN', readonly=True)
    company_tin = fields.Char(string='TIN', readonly=True)
    company_serial = fields.Char(string='EFD Serial', readonly=True)
    company_vin = fields.Char(string='VIN', readonly=True)
    tax_office = fields.Char(string='Tax Office', readonly=True)

    # Status
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('connected', 'Connected'),
        ('failed', 'Failed'),
    ], string='Connection Status', default='not_tested', readonly=True)
    last_connection = fields.Datetime(string='Last Successful Connection', readonly=True)

    go_live_date = fields.Date(
        string='TRA Go-Live Date',
        default=fields.Date.context_today,
        help='Invoices dated before this are not counted as missing a receipt on the dashboard.'
    )
    auto_generate_receipt = fields.Boolean(
        string='Generate Receipts Automatically',
        default=False,
        help='When enabled, a TRA receipt is generated as soon as a customer invoice is confirmed. '
             'Otherwise use the Generate TRA Receipt button on the invoice.'
    )

    _sql_constraints = [
        ('unique_active', 'CHECK(1=1)', 'Only one active configuration is recommended'),
    ]

    @api.model
    def get_active_config(self):
        # sudo: invoicing users need the API, but only managers may read the credentials
        config = self.sudo().search([('active', '=', True)], limit=1)
        if not config:
            raise UserError(_('No active TRA EFD configuration found. Please configure TRA EFD settings first.'))
        return config

    def _get_valid_token(self):
        """Return a valid bearer token, refreshing if expired."""
        self.ensure_one()
        now = datetime.now()
        if self.access_token and self.token_expiry:
            expiry = fields.Datetime.from_string(self.token_expiry)
            if expiry > now + timedelta(minutes=5):
                return self.access_token
        # Token missing or expired — re-authenticate
        return self._authenticate()

    def _authenticate(self):
        """Authenticate with the Zalongwa WebSHOP API and store the token."""
        self.ensure_one()
        url = f"{self.api_base_url}/login"
        try:
            resp = requests.post(
                url,
                data={'client_id': self.client_id, 'client_secret': self.client_secret},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            self.write({'connection_status': 'failed'})
            raise UserError(_('TRA EFD API connection failed: %s') % str(e))

        if 'access_token' not in data:
            self.write({'connection_status': 'failed'})
            raise UserError(_('TRA EFD authentication failed. Check your Client ID and Secret. (%s)',
                              data.get('message', '')))

        expiry = datetime.now() + timedelta(seconds=data.get('expires_in', 3600))
        self.write({
            'access_token': data['access_token'],
            'token_expiry': fields.Datetime.to_string(expiry),
            'token_user_name': data.get('name', ''),
            'token_email': data.get('email', ''),
            'connection_status': 'connected',
            'last_connection': fields.Datetime.now(),
        })
        return data['access_token']

    def action_test_connection(self):
        """Test API connection and fetch company profile."""
        self.ensure_one()
        token = self._authenticate()
        # Fetch company profile
        try:
            resp = requests.get(
                f"{self.api_base_url}/companyprofile",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self.write({
                'company_vrn': data.get('vrn', ''),
                'company_tin': data.get('tin', ''),
                'company_serial': data.get('serial', ''),
                'company_vin': data.get('vin', ''),
                'tax_office': data.get('taxoffice', ''),
            })
        except Exception as e:
            _logger.warning('Could not fetch company profile: %s', e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('TRA EFD Connection Successful'),
                'message': _('Connected as %s (%s)') % (self.token_user_name, self.token_email),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_refresh_token(self):
        self.ensure_one()
        self._authenticate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Refreshed'),
                'message': _('Access token has been refreshed successfully.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def _api_get(self, endpoint):
        """Generic GET request helper."""
        self.ensure_one()
        token = self._get_valid_token()
        url = f"{self.api_base_url}/{endpoint}"
        try:
            resp = requests.get(
                url,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            raise UserError(_('TRA EFD API error: %s') % str(e))

    def _api_post(self, endpoint, payload):
        """Generic POST request helper."""
        self.ensure_one()
        token = self._get_valid_token()
        url = f"{self.api_base_url}/{endpoint}"
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                timeout=60,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            raise TraEfdUncertainError(_('TRA EFD API did not respond: %s') % str(e))
        except requests.exceptions.RequestException as e:
            raise UserError(_('TRA EFD API error: %s') % str(e))

        if resp.status_code >= 500:
            raise TraEfdUncertainError(_('TRA EFD API error %s: %s') % (resp.status_code, resp.text[:500]))
        if resp.status_code >= 400:
            raise UserError(_('TRA EFD API error %s: %s') % (resp.status_code, resp.text[:500]))
        _logger.debug('API POST to %s successful. Response: %s', endpoint, resp.text)
        try:
            return resp.json()
        except ValueError:
            raise TraEfdUncertainError(_('TRA EFD API returned an unreadable response: %s') % resp.text[:500])
