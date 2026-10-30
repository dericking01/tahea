from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    restrict_stock_locations = fields.Boolean(
        string='Restrict Stock Locations',
        help="If checked, this user only sees the stock (on hand quantities, locations, warehouses, "
             "receipts and other operations) of the allowed locations below. "
             "Internal transfers and delivery orders stay visible to everyone.",
    )
    allowed_stock_location_ids = fields.Many2many(
        'stock.location', 'gw_user_allowed_location_rel', 'user_id', 'location_id',
        string='Allowed Stock Locations',
        domain=[('usage', 'in', ('internal', 'view'))],
        help="Locations (and their sub-locations) this user works with. They drive the "
             "'Custom Receipts' card of the Inventory Overview (receipt operation types whose "
             "destination is one of these locations) and, when 'Restrict Stock Locations' is "
             "checked, what the user can see. Select a warehouse's root location (e.g. 'WH') "
             "to include the whole warehouse.",
    )
    gw_responsible_location_ids = fields.Many2many(
        'stock.location', 'gw_location_responsible_rel', 'user_id', 'location_id',
        string='In Charge of Locations',
        domain=[('usage', 'in', ('internal', 'view'))],
        help="Locations for which this user confirms the reception of internal transfers.",
    )
