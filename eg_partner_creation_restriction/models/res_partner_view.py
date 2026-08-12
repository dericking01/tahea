from odoo import fields, models, api,_
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    access_user_partner_creation = fields.Boolean(compute='_compute_user_access')

    # def _compute_user_access(self):
    #     self.access_user_partner_creation, user = self.env.user.has_group(
    #         'eg_partner_creation_restriction.res_partner_view_edit_sequence')

    # @api.model
    # def create(self, vals):
    #     if self.env.user.has_group('eg_partner_creation_restriction.res_partner_view_edit_sequence'):
    #         raise UserError('You need to add a line before posting.')
    #     return super(ResPartner, self).create(vals)
    #
    #
    @api.model
    def create(self, vals):
        if self.env.user.has_group('eg_partner_creation_restriction.partner_creation_restriction_group'):
            raise UserError(_("You don't have access to create Contact."))
        else:
            return super(ResPartner, self).create(vals)
