from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    employee_signature = fields.Binary(
        string='Signature', copy=False, attachment=True,
        help="Signature of the employee, drawn with the mouse or by hand on a touch screen.")
    employee_signed_on = fields.Datetime(string='Signed On', copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_signature'):
                vals['employee_signed_on'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        if 'employee_signature' in vals:
            vals['employee_signed_on'] = fields.Datetime.now() if vals['employee_signature'] else False
        return super().write(vals)
