from odoo import api, fields, models


class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', 'employee.user.mixin']

    buyer_employee_id = fields.Many2one(
        'hr.employee',
        string='Buyer',
        compute='_compute_buyer_employee_id',
        inverse='_inverse_buyer_employee_id',
        store=True, readonly=False,
        domain="[('company_id', 'in', (company_id, False))]",
        help="Any employee can be picked here, including ones without a "
             "login yet. If the employee has no login, one is created "
             "automatically and granted Purchase access.",
    )

    @api.depends('user_id')
    def _compute_buyer_employee_id(self):
        for requisition in self:
            requisition.buyer_employee_id = self.env['hr.employee'].search(
                [('user_id', '=', requisition.user_id.id)], limit=1
            ) if requisition.user_id else False

    def _inverse_buyer_employee_id(self):
        for requisition in self:
            employee = requisition.buyer_employee_id
            if not employee:
                requisition.user_id = False
                continue
            requisition.user_id = requisition._get_or_create_employee_login(
                employee, extra_group_xmlids=['purchase.group_purchase_user'],
            )
