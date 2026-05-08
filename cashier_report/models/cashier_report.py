from odoo import models, fields, api

class CashierReport(models.Model):
    _name = "cashier.report"
    _description = "Cashier Report"
    _order = "date desc"

    name = fields.Char(string="Report No.", copy=False, readonly=True)
    date = fields.Date(string="Report Date", default=fields.Date.context_today)
    shop_id = fields.Many2one(
    'pos.config',
    string="Shop",
    required=True,
    ondelete="restrict"
)

    sale_type = fields.Selection([
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail')
    ], string="Sale Type", required=True)
    employee_id = fields.Many2one('hr.employee', string="Cashier", required=True)
    total_sales = fields.Monetary(string="Total Sales", compute="_compute_total", store=True)
    currency_id = fields.Many2one("res.currency", string="Currency",
                                  default=lambda self: self.env.company.currency_id.id)
    line_ids = fields.One2many('cashier.report.line', 'report_id', string="Transactions",  ondelete='cascade')
    expenditure_ids = fields.One2many('cashier.expenditure', 'report_id', string="Expenditures",  ondelete='cascade')
    total_expenditure = fields.Monetary(string="Total Expenditure", compute="_compute_total_expenditure", store=True)
    balance = fields.Monetary(string="Balance", compute="_compute_balance", store=True)
    

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_sales = sum(rec.line_ids.mapped('amount'))

    @api.depends('expenditure_ids.amount')
    def _compute_total_expenditure(self):
        for rec in self:
            rec.total_expenditure = sum(rec.expenditure_ids.mapped('amount'))

    @api.depends('total_sales', 'total_expenditure')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.total_sales - rec.total_expenditure

    # ✅ Override create to assign sequence
    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cashier.report') or 'New'
        return super(CashierReport, self).create(vals)
    
      # ✅ Smart Button Actions
    def action_view_transactions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transactions',
            'view_mode': 'tree,form',
            'res_model': 'cashier.report.line',
            'domain': [('report_id', '=', self.id)],
            'context': dict(self.env.context, default_report_id=self.id),
        }

    def action_view_expenditures(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expenditures',
            'view_mode': 'tree,form',
            'res_model': 'cashier.expenditure',
            'domain': [('report_id', '=', self.id)],
            'context': dict(self.env.context, default_report_id=self.id),
        }

    def action_view_balance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cashier Balance',
            'view_mode': 'form',
            'res_model': 'cashier.report',
            'res_id': self.id,
        }


class CashierExpenditure(models.Model):
    _name = "cashier.expenditure"
    _description = "Cashier Expenditure"

    report_id = fields.Many2one('cashier.report', string="Report", ondelete="cascade")
    description = fields.Char(string="Description", required=True)
    amount = fields.Monetary(string="Amount", required=True)
    currency_id = fields.Many2one(related="report_id.currency_id", store=True, readonly=True)


class CashierShop(models.Model):
    _name = "cashier.shop"
    _description = "Cashier Shop"

    name = fields.Char(string="Shop Name", required=True)
    code = fields.Char(string="Shop Code")
    location = fields.Char(string="Location")
    active = fields.Boolean(string="Active", default=True)

    # Optional: link cashier reports
    report_ids = fields.One2many('cashier.report', 'shop_id', string="Reports")