from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
        sales_group = self.env.ref('sales_team.group_sale_salesman')
        internal_group = self.env.ref('base.group_user')
        for order in self:
            employee = order.salesperson_employee_id
            if not employee:
                order.user_id = False
                continue
            user = employee.user_id
            if not user:
                if not employee.work_email:
                    raise UserError(_(
                        "%(employee)s has no login and no work email set, so a "
                        "user account can't be created automatically. Please "
                        "set a work email on the employee first.",
                        employee=employee.name,
                    ))
                user = self.env['res.users'].with_context(no_reset_password=True).create({
                    'name': employee.name,
                    'login': employee.work_email,
                    'email': employee.work_email,
                    'company_id': (employee.company_id or order.company_id).id,
                    'company_ids': [(6, 0, (employee.company_id | order.company_id).ids)],
                    'groups_id': [(6, 0, (internal_group | sales_group).ids)],
                })
                employee.user_id = user
                order.message_post(body=_(
                    "A new user login was created for %(employee)s so they "
                    "could be assigned as Salesperson.",
                    employee=employee.name,
                ))
            elif not user.has_group('sales_team.group_sale_salesman'):
                user.write({'groups_id': [(4, sales_group.id)]})
            order.user_id = user
