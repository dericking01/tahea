from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LicenseSubscription(models.Model):
    _name = "license.subscription"
    _description = "License & Subscription"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------
    # Basic Info
    # -------------------------
    name = fields.Char(required=True, tracking=True)
    type = fields.Selection([
        ('business', 'Business License'),
        ('extention', 'Extention'),
        ('probation', 'Probation'),
        ('contract', 'Contracts'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    ], required=True, default='contract', tracking=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor", tracking=True)
    responsible_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, tracking=True
    )
    note = fields.Text()
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    cost = fields.Float(string="Value", tracking=True)

    # -------------------------
    # Subscription Dates
    # -------------------------
    start_date = fields.Date(default=fields.Date.today, tracking=True)
    expiry_date = fields.Date(required=True, tracking=True)
    period_months = fields.Integer(
        string="Subscription Period (Months)",
        default=12,
        help="Enter how many months the subscription is valid",
        tracking=True
    )
    reminder_days = fields.Integer(default=14, help="Days before expiry to remind")

    # -------------------------
    # Related Lines
    # -------------------------
    subscription_line_ids = fields.One2many(
        'license.subscription.line', 'subscription_id', string="Subscription Lines"
    )

    # -------------------------
    # Computed Fields
    # -------------------------
    state = fields.Selection([
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], compute="_compute_state", store=True, tracking=True)

    show_renew_button = fields.Boolean(compute="_compute_show_renew_button")

    # -------------------------
    # Onchange Methods
    # -------------------------
    @api.onchange('start_date', 'period_months')
    def _onchange_start_date_period(self):
        """Automatically fill expiry_date based on start_date + period_months"""
        for rec in self:
            if rec.start_date and rec.period_months:
                rec.expiry_date = rec.start_date + relativedelta(months=rec.period_months)

    # -------------------------
    # Compute Methods
    # -------------------------
    @api.depends('expiry_date', 'reminder_days')
    def _compute_state(self):
        """Compute subscription state based on expiry date and reminder_days"""
        today = date.today()
        for rec in self:
            if not rec.expiry_date:
                rec.state = 'active'
            elif rec.expiry_date < today:
                rec.state = 'expired'
            elif rec.expiry_date <= today + relativedelta(days=rec.reminder_days):
                rec.state = 'expiring'
            else:
                rec.state = 'active'

    @api.depends('state')
    def _compute_show_renew_button(self):
        """Show renew button only if subscription is expired"""
        for rec in self:
            rec.show_renew_button = rec.state == 'expired'

    # -------------------------
    # Action Methods
    # -------------------------
    def action_renew(self):
        """Renew subscription: set start_date to today and update expiry_date"""
        for rec in self:
            if rec.state == 'expired':
                months = rec.period_months or 12
                new_start = date.today()
                new_expiry = new_start + relativedelta(months=months)
                rec.write({
                    'start_date': new_start,
                    'expiry_date': new_expiry,
                })
                rec.message_post(
                    body=f"Subscription renewed. Start Date: {new_start}, Expiry Date: {new_expiry}"
                )
            else:
                rec.message_post(body="Subscription is still active; renewal not needed.")

    def cron_check_expiry(self):
        """Send reminder email if subscription is expiring soon or expired"""
        today = date.today()
        records = self.search([('expiry_date', '!=', False)])
        template = self.env.ref('license_expiry_manager.email_template_license_expiry')
        for rec in records:
            remind_date = rec.expiry_date - relativedelta(days=rec.reminder_days)
            if today == remind_date or today == rec.expiry_date:
                if rec.responsible_id and rec.responsible_id.email:
                    template.send_mail(rec.id, force_send=True)


class LicenseSubscriptionLine(models.Model):
    _name = "license.subscription.line"
    _description = "License Subscription Line"

    subscription_id = fields.Many2one(
        'license.subscription', string="Subscription", required=True, ondelete='cascade'
    )
    name = fields.Char(string="Activity Name", required=True, tracking=True)
    start_date = fields.Date(string="Start Date", required=True, tracking=True)
    end_date = fields.Date(string="End Date", required=True, tracking=True)
    cost = fields.Float(string="Cost", tracking=True)
    status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string="Status", default='in_progress')

