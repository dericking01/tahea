from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_reimbursement_expense_visible = fields.Boolean(
        string="Reimbursement Expense",
        implied_group='hr_employee_extended.group_reimbursement_expense_visible',
        help="Show the Reimbursement Expense field on employee contracts.",
    )
    group_tuico_visible = fields.Boolean(
        string="TUICO",
        implied_group='hr_employee_extended.group_tuico_visible',
        help="Show the TUICO field on employee contracts.",
    )
