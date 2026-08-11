from odoo import api, fields, models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'employee.user.mixin']

    salesperson_employee_id = fields.Many2one(
        'hr.employee',
        string='Salesperson',
        compute='_compute_salesperson_employee_id',
        inverse='_inverse_salesperson_employee_id',
        store=True, readonly=False,
        domain="[('company_id', 'in', (company_id, False))]",
        help="Any employee can be picked here, including ones without a "
             "login yet. If the employee has no login, one is created "
             "automatically and granted Sales access.",
    )

    @api.depends('user_id')
    def _compute_salesperson_employee_id(self):
        for order in self:
            order.salesperson_employee_id = self.env['hr.employee'].search(
                [('user_id', '=', order.user_id.id)], limit=1
            ) if order.user_id else False

    def _inverse_salesperson_employee_id(self):
        for order in self:
            employee = order.salesperson_employee_id
            if not employee:
                order.user_id = False
                continue
            order.user_id = order._get_or_create_employee_login(
                employee, extra_group_xmlids=['sales_team.group_sale_salesman'],
            )
