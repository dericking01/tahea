from odoo import models, fields, api

class ContractContract(models.Model):
    _name = 'contract.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Contract'

    name = fields.Char(string='Contract Number', required=True)
    title = fields.Char(string='Contract Title', required=True)
    contract_date = fields.Date(string='Contract Date', required=True, default=fields.Date.today)

    order_ids = fields.One2many('contract.order', 'contract_id', string='Orders')


class ContractOrder(models.Model):
    _name = 'contract.order'
    _description = 'Contract Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    contract_id = fields.Many2one('contract.contract', string='Contract', required=True, ondelete='cascade')
    title = fields.Char(string='Order Title', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='pending', tracking=True)

    expired = fields.Boolean(string='Expired', compute='_compute_expired', store=True)

    @api.depends('end_date')
    def _compute_expired(self):
        today = fields.Date.today()
        for record in self:
            record.expired = record.end_date and record.end_date < today

    def check_upcoming_expiry(self):
        """CRON job to notify about soon-to-expire orders"""
        today = fields.Date.today()
        upcoming = today + timedelta(days=5)
        orders = self.search([
            ('end_date', '<=', upcoming),
            ('end_date', '>=', today),
            ('status', '!=', 'completed')
        ])
        for order in orders:
            order.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f"Order '{order.title}' will expire soon!",
                user_id=order.contract_id.create_uid.id,  # or a manager
                date_deadline=order.end_date,
            )
