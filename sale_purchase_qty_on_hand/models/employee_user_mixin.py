from odoo import _, models
from odoo.exceptions import UserError


class EmployeeUserMixin(models.AbstractModel):
    _name = 'employee.user.mixin'
    _description = 'Resolve or auto-create a login for an employee'

    def _get_or_create_employee_login(self, employee, extra_group_xmlids=()):
        """Return employee.user_id, creating one automatically if missing.

        Grants the groups in `extra_group_xmlids` (in addition to Internal
        User) on creation, and tops up an existing login with any of those
        groups it doesn't already have. Raises UserError if the employee
        has no work email to use as a login.
        """
        self.ensure_one()
        user = employee.user_id
        extra_groups = self.env['res.groups']
        for xmlid in extra_group_xmlids:
            extra_groups |= self.env.ref(xmlid)

        if not user:
            if not employee.work_email:
                raise UserError(_(
                    "%(employee)s has no login and no work email set, so a "
                    "user account can't be created automatically. Please "
                    "set a work email on the employee first.",
                    employee=employee.name,
                ))
            internal_group = self.env.ref('base.group_user')
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': employee.name,
                'login': employee.work_email,
                'email': employee.work_email,
                'company_id': (employee.company_id or self.env.company).id,
                'company_ids': [(6, 0, (employee.company_id | self.env.company).ids)],
                'groups_id': [(6, 0, (internal_group | extra_groups).ids)],
            })
            employee.user_id = user
            self.message_post(body=_(
                "A new user login was created for %(employee)s so they "
                "could be assigned to this record.",
                employee=employee.name,
            ))
        else:
            missing_groups = extra_groups - user.groups_id
            if missing_groups:
                user.write({'groups_id': [(4, group.id) for group in missing_groups]})
        return user
