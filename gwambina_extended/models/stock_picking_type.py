from odoo import _, api, fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    gw_receipt_confirmation = fields.Boolean(
        string='Receipt Confirmation by Destination',
        help="Internal transfers of this type are first dispatched to the transit location. "
             "The person in charge of the destination location then confirms the quantities "
             "physically received before they are added to the destination stock. "
             "Only applies when the destination location has persons in charge.",
    )

    # -------------------------------------------------------------------------
    # "Custom Receipts" card of the Inventory Overview
    # -------------------------------------------------------------------------

    @api.model
    def _gw_custom_receipt_locations(self):
        return self.env.user.allowed_stock_location_ids.filtered(
            lambda l: l.active and l.usage in ('internal', 'view'))

    @api.model
    def _gw_custom_receipts_domain(self):
        """ GRNs (receipts) whose destination is one of the current user's allowed locations:
        receipt operation types (code 'incoming' or named "Receipt..."), receipt
        confirmations of internal transfers excluded. """
        locations = self._gw_custom_receipt_locations()
        if not locations:
            return [(0, '=', 1)]
        return [
            ('location_dest_id', 'child_of', locations.ids),
            ('gw_is_receipt_confirmation', '=', False),
            '|', ('picking_type_code', '=', 'incoming'), ('picking_type_id.name', '=ilike', 'receipt%'),
        ]

    @api.model
    def gw_get_custom_receipts_data(self):
        if not self._gw_custom_receipt_locations():
            return {'show': False, 'ready': 0}
        Picking = self.env['stock.picking']
        domain = self._gw_custom_receipts_domain()
        return {
            'show': True,
            'ready': Picking.search_count(domain + [('state', '=', 'assigned')]),
        }

    @api.model
    def gw_action_custom_receipts(self):
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action.update({
            'name': _('Custom Receipts'),
            'domain': self._gw_custom_receipts_domain(),
            'context': {'contact_display': 'partner_address', 'create': False},
        })
        for key in ('path', 'help'):
            action.pop(key, None)
        return action
