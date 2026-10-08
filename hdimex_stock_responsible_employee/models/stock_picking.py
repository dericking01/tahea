# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    responsible_employee_id = fields.Many2one(
        'hr.employee', string='Responsible Employee', tracking=True, copy=False,
        default=lambda self: self.env.user.employee_id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Employee responsible for this transfer. If the employee has a "
             "linked user, that user is also set as the transfer's user responsible.",
    )

    @api.onchange('responsible_employee_id')
    def _onchange_responsible_employee_id(self):
        for picking in self:
            picking.user_id = picking.responsible_employee_id.sudo().user_id

    def _hdimex_sync_responsible(self, vals):
        """Keep user_id and responsible_employee_id consistent in ``vals``."""
        vals = dict(vals)
        if 'responsible_employee_id' in vals:
            employee = self.env['hr.employee'].sudo().browse(vals['responsible_employee_id'])
            vals['user_id'] = employee.user_id.id
        elif vals.get('user_id'):
            company_id = vals.get('company_id') or (self.company_id[:1].id if self else self.env.company.id)
            employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', vals['user_id']),
                ('company_id', '=', company_id),
            ], limit=1)
            vals['responsible_employee_id'] = employee.id
        elif 'user_id' in vals:
            vals['responsible_employee_id'] = False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._hdimex_sync_responsible(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if 'responsible_employee_id' in vals or 'user_id' in vals:
            vals = self._hdimex_sync_responsible(vals)
        return super().write(vals)
