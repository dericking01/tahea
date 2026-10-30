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
    def _gw_custom_receipt_types(self):
        """ Receipt operation types (code 'incoming', or named "Receipt...") whose default
        destination is one of the current user's allowed stock locations. """
        locations = self.env.user.allowed_stock_location_ids
        if not locations:
            return self.browse()
        return self.search([
            ('default_location_dest_id', 'child_of', locations.ids),
            '|', ('code', '=', 'incoming'), ('name', '=ilike', 'receipt%'),
        ])

    @api.model
    def gw_get_custom_receipts_data(self):
        types = self._gw_custom_receipt_types()
        return {
            'show': bool(self.env.user.allowed_stock_location_ids),
            'type_count': len(types),
            'ready': sum(types.mapped('count_picking_ready')),
            'waiting': sum(types.mapped('count_picking_waiting')),
            'late': sum(types.mapped('count_picking_late')),
        }

    @api.model
    def gw_action_custom_receipts(self):
        action = self.env['ir.actions.act_window']._for_xml_id('stock.stock_picking_type_action')
        action.update({
            'name': _('Custom Receipts'),
            'domain': [('id', 'in', self._gw_custom_receipt_types().ids)],
            'context': {'gw_hide_custom_receipts_card': True},
        })
        action.pop('path', None)
        return action

    @api.model
    def gw_action_custom_receipts_pickings(self, state=None):
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        domain = [('picking_type_id', 'in', self._gw_custom_receipt_types().ids)]
        if state == 'late':
            domain += [('scheduled_date', '<', fields.Datetime.now()),
                       ('state', 'in', ('assigned', 'waiting', 'confirmed'))]
        elif state == 'waiting':
            domain += [('state', 'in', ('confirmed', 'waiting'))]
        elif state:
            domain += [('state', '=', state)]
        action.update({
            'name': _('Custom Receipts'),
            'domain': domain,
            'context': {'contact_display': 'partner_address', 'create': False},
        })
        action.pop('path', None)
        return action
