# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ReVendorContract(models.Model):
    _name = 're.vendor.contract'
    _description = 'Vendor / Contractor Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_end'

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char()
    partner_id = fields.Many2one('res.partner', 'Contractor', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    contract_type = fields.Selection([
        ('maintenance', 'Maintenance Agreement'), ('sla', 'Service Level Agreement'), ('framework', 'Framework / Rates'),
        ('construction', 'Construction'), ('cleaning', 'Cleaning / Security Services'), ('other', 'Other')],
        default='maintenance', required=True)
    service_category_ids = fields.Many2many('re.service.category', string='Services')
    property_ids = fields.Many2many('re.property', string='Properties Covered')
    equipment_ids = fields.One2many('maintenance.equipment', 're_service_contract_id', 'Equipment Covered')
    date_start = fields.Date(required=True, tracking=True)
    date_end = fields.Date(tracking=True)
    value = fields.Monetary('Contract Value (annual)')
    pricing = fields.Html('Agreed Pricing / Rates')
    payment_term_id = fields.Many2one('account.payment.term')
    response_time_hours = fields.Float('SLA Response Time (h)')
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired'),
                              ('terminated', 'Terminated')], default='draft', tracking=True)
    days_to_expiry = fields.Integer(compute='_compute_days')

    def _compute_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_expiry = (rec.date_end - today).days if rec.date_end else 9999

    def action_activate(self):
        self.write({'state': 'active'})

    def action_terminate(self):
        self.write({'state': 'terminated'})

    @api.model
    def _cron_contract_expiry(self):
        today = fields.Date.context_today(self)
        self.search([('state', '=', 'active'), ('date_end', '<', today)]).write({'state': 'expired'})
        for rec in self.search([('state', '=', 'active'), ('date_end', '!=', False),
                                ('date_end', '<=', today + timedelta(days=60))]):
            if not rec.activity_ids:
                rec.activity_schedule('mail.mail_activity_data_todo', date_deadline=rec.date_end,
                                      summary=_('Contract expires on %s', rec.date_end))


class ReVendorLicense(models.Model):
    _name = 're.vendor.license'
    _description = 'Contractor Licence / Registration'
    _order = 'expiry_date'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    license_type = fields.Selection([
        ('crb', 'CRB Contractor Registration'), ('ewura', 'EWURA Licence'), ('erb', 'ERB / Professional Registration'),
        ('business', 'Business Licence'), ('fire', 'Fire Safety Certificate'), ('osha', 'OSHA Compliance'),
        ('tax_clearance', 'Tax Clearance'), ('other', 'Other')], required=True)
    number = fields.Char(required=True)
    authority = fields.Char()
    grade = fields.Char('Class / Grade')
    issue_date = fields.Date()
    expiry_date = fields.Date()
    attachment_ids = fields.Many2many('ir.attachment', string='Copy')
    is_valid = fields.Boolean(compute='_compute_valid')

    def _compute_valid(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_valid = not rec.expiry_date or rec.expiry_date >= today
