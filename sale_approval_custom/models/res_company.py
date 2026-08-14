from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sale_approval_required = fields.Boolean(
        string='Sales Approval Required',
        default=False,
    )

    sale_approval_user_ids = fields.Many2many(
        'res.users',
        'res_company_sale_approval_user_rel',
        'company_id',
        'user_id',
        string='Sales Approvers',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'sale_approval_required' in vals:
            group = self.env.ref('sale_approval_custom.group_sale_approval_menu', raise_if_not_found=False)
            if group:
                for company in self:
                    users = self.env['res.users'].search([('company_id', '=', company.id)])
                    if company.sale_approval_required:
                        group.sudo().write({'users': [(4, user.id) for user in users]})
                    else:
                        group.sudo().write({'users': [(3, user.id) for user in users]})
        return res