from odoo import api, fields, models
from odoo.osv import expression


class StockLocation(models.Model):
    _name = 'stock.location'
    _inherit = ['stock.location', 'gw.location.restriction.mixin']

    gw_responsible_user_ids = fields.Many2many(
        'res.users', 'gw_location_responsible_rel', 'location_id', 'user_id',
        string='Persons in Charge',
        help="Users who confirm the reception of internal transfers sent to this location "
             "(or to any of its sub-locations). Leave empty for a direct transfer without "
             "reception confirmation.",
    )

    @api.model
    def _gw_location_restriction_domain(self, locations):
        # Only internal locations are restricted: partner, transit, virtual... stay visible.
        return ['|', ('usage', '!=', 'internal'), ('id', 'child_of', locations.ids)]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Location pickers flagged with this context key (e.g. the source of a transfer)
        # only propose the allowed locations to restricted users.
        if self.env.context.get('gw_restrict_locations'):
            args = self._gw_restrict_domain(args or [])
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    def _gw_get_responsible_users(self):
        """ Persons in charge of this location, inherited from its parent locations. """
        self.ensure_one()
        return self.sudo().search([('id', 'parent_of', self.id)]).gw_responsible_user_ids
