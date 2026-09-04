# Copyright © from 2018 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import fields, models
from odoo.osv.expression import AND


class PosConfig(models.Model):
    _inherit = 'pos.config'

    basic_employee_ids = fields.Many2many(
        help='If left empty, only the employee linked to the user opening the '
             'register can log in. Select the employees allowed to log in with basic access.',
    )

    def _employee_domain(self, user_id):
        """Restrict the "Log in with Employees" list to the employees explicitly
        selected under Basic/Advanced rights, instead of falling back to all
        company employees when Basic rights is left empty.

        The employee linked to the user opening the register is always kept
        so the register can never end up without anyone able to log in.
        """
        domain = self._check_company_domain(self.company_id)
        domain = AND([
            domain,
            ['|', ('user_id', '=', user_id), ('id', 'in', self.basic_employee_ids.ids + self.advanced_employee_ids.ids)]
        ])
        return domain
