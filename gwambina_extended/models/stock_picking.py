from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Receipt confirmation of internal transfers
    gw_is_receipt_confirmation = fields.Boolean(
        string='Receipt Confirmation', readonly=True, index=True,
        help="Transfer from the transit location to the destination, to be confirmed by the "
             "person in charge of the destination location.")
    gw_dispatch_picking_id = fields.Many2one(
        'stock.picking', string='Dispatched By', readonly=True, index='btree_not_null',
        help="Internal transfer that dispatched these goods from the source location.")
    gw_return_location_id = fields.Many2one(
        'stock.location', string='Original Source Location', readonly=True,
        help="Location the goods come from; undelivered goods can be returned there.")
    gw_returned_to_source = fields.Boolean(string='Returned to Source', readonly=True)
    gw_final_location_id = fields.Many2one(
        'stock.location', string='Final Destination', readonly=True, copy=False,
        help="Destination of the goods, awaiting the receipt confirmation.")
    gw_receipt_picking_ids = fields.One2many(
        'stock.picking', 'gw_dispatch_picking_id', string='Receipt Confirmations')
    gw_receipt_picking_count = fields.Integer(compute='_compute_gw_receipt_picking_count')
    gw_responsible_user_ids = fields.Many2many(
        'res.users', string='Persons in Charge of Reception', compute='_compute_gw_responsible_user_ids')
    gw_can_delete_moves = fields.Boolean(compute='_compute_gw_can_delete_moves')

    @api.depends('picking_type_code')
    @api.depends_context('uid')
    def _compute_gw_can_delete_moves(self):
        is_admin = self.env.user.has_group('base.group_system')
        for picking in self:
            picking.gw_can_delete_moves = is_admin or picking.picking_type_code != 'incoming'

    @api.depends('gw_receipt_picking_ids')
    def _compute_gw_receipt_picking_count(self):
        for picking in self:
            picking.gw_receipt_picking_count = len(picking.gw_receipt_picking_ids)

    @api.depends('location_dest_id', 'gw_is_receipt_confirmation')
    def _compute_gw_responsible_user_ids(self):
        for picking in self:
            if picking.gw_is_receipt_confirmation and picking.location_dest_id:
                picking.gw_responsible_user_ids = picking.location_dest_id._gw_get_responsible_users()
            else:
                picking.gw_responsible_user_ids = False

    # -------------------------------------------------------------------------
    # Line deletion on receipts (admin only)
    # -------------------------------------------------------------------------

    def write(self, vals):
        if (
            not self.env.su
            and any(p.picking_type_code == 'incoming' for p in self)
            and self._gw_vals_remove_moves(vals)
            and not self.env.user.has_group('base.group_system')
        ):
            raise UserError(_("Only an administrator can delete lines of a receipt."))
        return super().write(vals)

    def _gw_vals_remove_moves(self, vals):
        for fname in ('move_ids', 'move_ids_without_package'):
            for cmd in vals.get(fname) or []:
                if not isinstance(cmd, (list, tuple)) or not cmd:
                    continue
                if cmd[0] in (Command.DELETE, Command.UNLINK, Command.CLEAR):
                    return True
                if cmd[0] == Command.SET and any(set(p[fname].ids) - set(cmd[2] or []) for p in self):
                    return True
        return False

    # -------------------------------------------------------------------------
    # Validation checks
    # -------------------------------------------------------------------------

    def _pre_action_done_hook(self):
        if not self.env.context.get('gw_skip_stock_check'):
            self._gw_check_stock_availability()
            self._gw_check_purchase_receipt_qty()
        return super()._pre_action_done_hook()

    def _gw_moves_to_process(self):
        """ Moves that the validation will actually process (same rule as the standard
        `_pre_action_done_hook`: picked moves if any are picked, else moves with a quantity). """
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel') and not m.scrapped and m.quantity)
        if any(m.picked for m in moves):
            moves = moves.filtered('picked')
        return moves

    def _gw_check_stock_availability(self):
        """ Deliveries and internal transfers: list ALL products whose processed quantity
        exceeds the quantity on hand in the source location, in a single error. """
        pickings = self.filtered(lambda p: p.picking_type_code in ('outgoing', 'internal') and p.location_id.usage == 'internal')
        if not pickings:
            return
        Quant = self.env['stock.quant'].sudo()
        uom_precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        requested = defaultdict(float)
        key_pickings = defaultdict(lambda: self.env['stock.picking'])
        for picking in pickings:
            for move in picking._gw_moves_to_process().filtered(lambda m: m.product_id.is_storable):
                lines = move.move_line_ids.filtered('quantity')
                if lines:
                    for ml in lines:
                        key = (ml.product_id, ml.location_id, ml.lot_id)
                        requested[key] += ml.quantity_product_uom
                        key_pickings[key] |= picking
                else:
                    key = (move.product_id, move.location_id, self.env['stock.lot'])
                    requested[key] += move.product_qty
                    key_pickings[key] |= picking

        shortages = []
        for (product, location, lot), qty in requested.items():
            domain = [('product_id', '=', product.id), ('location_id', 'child_of', location.id)]
            if lot:
                domain.append(('lot_id', '=', lot.id))
            on_hand = sum(Quant.search(domain).mapped('quantity'))
            if float_compare(qty, on_hand, precision_digits=uom_precision) > 0:
                shortages.append((key_pickings[(product, location, lot)], product, location, lot, qty, max(on_hand, 0.0)))
        if not shortages:
            return

        lines = []
        for picks, product, location, lot, qty, on_hand in sorted(shortages, key=lambda s: (s[0][:1].name or '', s[1].display_name)):
            lines.append(_(
                "- %(product)s%(lot)s in %(location)s: requested %(qty)s %(uom)s, available %(on_hand)s %(uom)s (%(pickings)s)",
                product=product.display_name,
                lot=_(" (Lot/Serial %s)", lot.name) if lot else "",
                location=location.display_name,
                qty=float_round(qty, precision_digits=uom_precision),
                on_hand=float_round(on_hand, precision_digits=uom_precision),
                uom=product.uom_id.name,
                pickings=", ".join(picks.mapped('name')),
            ))
        raise UserError(_(
            "Insufficient stock. The requested quantity exceeds the quantity available for the following %(count)s product(s):\n\n%(lines)s",
            count=len(lines), lines="\n".join(lines)))

    def _gw_check_purchase_receipt_qty(self):
        """ Receipts (GRN) from a purchase order: the received quantity cannot exceed the ordered
        quantity of the PO line. All exceeding lines are reported at once. """
        errors = []
        for picking in self.filtered(lambda p: p.picking_type_code == 'incoming'):
            receiving = defaultdict(float)
            for move in picking._gw_moves_to_process():
                if move.purchase_line_id and move.location_id.usage == 'supplier':
                    pol = move.purchase_line_id
                    receiving[pol] += move.product_uom._compute_quantity(move.quantity, pol.product_uom, rounding_method='HALF-UP')
            for pol, qty in receiving.items():
                total = pol.qty_received + qty
                if float_compare(total, pol.product_qty, precision_rounding=pol.product_uom.rounding) > 0:
                    errors.append(_(
                        "- %(product)s: ordered %(ordered)s %(uom)s, already received %(received)s, receiving now %(qty)s (%(po)s / %(picking)s)",
                        product=pol.product_id.display_name,
                        ordered=pol.product_qty, uom=pol.product_uom.name,
                        received=pol.qty_received, qty=qty,
                        po=pol.order_id.name, picking=picking.name,
                    ))
        if errors:
            raise UserError(_(
                "You cannot receive more than the quantity ordered on the purchase order:\n\n%s",
                "\n".join(errors)))

    # -------------------------------------------------------------------------
    # Receipt confirmation of internal transfers
    # -------------------------------------------------------------------------

    def _gw_needs_receipt_confirmation(self):
        self.ensure_one()
        return bool(
            not self.env.context.get('gw_skip_receipt_confirmation')
            and self.picking_type_id.gw_receipt_confirmation
            and not self.gw_is_receipt_confirmation
            and self.picking_type_code == 'internal'
            and self.location_id.usage == 'internal'
            and self.location_dest_id.usage == 'internal'
            and self.company_id.internal_transit_location_id
            and not self.move_ids.move_dest_ids
            and self.location_dest_id._gw_get_responsible_users()
        )

    def _gw_check_can_confirm_receipt(self):
        user = self.env.user
        if self.env.su or user.has_group('base.group_system'):
            return
        for picking in self.filtered('gw_is_receipt_confirmation'):
            responsibles = picking.location_dest_id._gw_get_responsible_users()
            if responsibles and user not in responsibles:
                raise UserError(_(
                    "Only the person(s) in charge of %(location)s can confirm the reception of %(picking)s: %(users)s",
                    location=picking.location_dest_id.display_name,
                    picking=picking.name,
                    users=", ".join(responsibles.mapped('name')),
                ))

    def button_validate(self):
        self.filtered(lambda p: p.state != 'done')._gw_check_can_confirm_receipt()
        return super().button_validate()

    def _check_backorder(self):
        # Goods sitting in transit must never be dropped: the remainder of a receipt
        # confirmation always goes to a backorder (no "No Backorder" option).
        return super(StockPicking, self.filtered(lambda p: not p.gw_is_receipt_confirmation))._check_backorder()

    def _action_done(self):
        confirmations = self.filtered('gw_is_receipt_confirmation')
        to_dispatch = (self - confirmations).filtered(lambda p: p._gw_needs_receipt_confirmation())
        final_locations = {}
        for picking in to_dispatch:
            final_locations[picking] = picking.location_dest_id
            transit = picking.company_id.internal_transit_location_id
            picking.write({'location_dest_id': transit.id, 'gw_final_location_id': picking.location_dest_id.id})
            picking.move_line_ids.write({'location_dest_id': transit.id})

        if confirmations:
            super(StockPicking, confirmations.with_context(cancel_backorder=False))._action_done()
            confirmations.filtered(lambda p: p.state == 'done').activity_feedback(['mail.mail_activity_data_todo'])
        res = super(StockPicking, self - confirmations)._action_done()

        for picking, final_location in final_locations.items():
            # Undispatched remainder (backorder) keeps going to the real destination.
            backorders = self.search([('backorder_id', '=', picking.id), ('state', 'not in', ('done', 'cancel'))])
            for backorder in backorders:
                backorder.write({'location_dest_id': final_location.id})
                backorder.move_line_ids.write({'location_dest_id': final_location.id})
            picking._gw_create_receipt_confirmation(final_location)
        return res

    def _gw_create_receipt_confirmation(self, final_location):
        self.ensure_one()
        transit = self.company_id.internal_transit_location_id
        done_moves = self.move_ids.filtered(lambda m: m.state == 'done' and m.quantity)
        if not done_moves:
            return self.env['stock.picking']
        warehouse = final_location.warehouse_id or self.picking_type_id.warehouse_id
        picking_type = warehouse._gw_get_receipt_confirm_type() if warehouse else self.picking_type_id
        receipt = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': transit.id,
            'location_dest_id': final_location.id,
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'gw_is_receipt_confirmation': True,
            'gw_dispatch_picking_id': self.id,
            'gw_return_location_id': self.location_id.id,
            'move_ids': [Command.create({
                'name': move.name,
                'product_id': move.product_id.id,
                'product_uom': move.product_uom.id,
                'product_uom_qty': move.quantity,
                'location_id': transit.id,
                'location_dest_id': final_location.id,
                'company_id': self.company_id.id,
                'picking_type_id': picking_type.id,
                'description_picking': move.description_picking,
            }) for move in done_moves],
        })
        receipt.action_confirm()
        receipt.action_assign()
        self.message_post(body=_(
            "Goods dispatched to %(transit)s. Reception at %(location)s to be confirmed on %(receipt)s.",
            transit=transit.display_name, location=final_location.display_name,
            receipt=receipt._get_html_link()))
        receipt._gw_schedule_confirmation_activities()
        return receipt

    def _gw_schedule_confirmation_activities(self):
        for picking in self:
            for user in picking.location_dest_id._gw_get_responsible_users():
                picking.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=_("Confirm reception at %s", picking.location_dest_id.display_name),
                    note=_("Check the goods physically received against %s and validate. "
                           "Undelivered quantities go to a backorder.", picking.name),
                )

    def _create_backorder(self, backorder_moves=None):
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        backorders.filtered('gw_is_receipt_confirmation')._gw_schedule_confirmation_activities()
        return backorders

    def action_gw_return_to_source(self):
        """ Goods that will never be delivered: send them from transit back to the original
        source location, where its person in charge confirms the reception. """
        user = self.env.user
        for picking in self:
            if not picking.gw_is_receipt_confirmation or picking.state in ('done', 'cancel'):
                raise UserError(_("Only pending receipt confirmations can be returned to their source location."))
            if picking.gw_returned_to_source:
                raise UserError(_("%s is already being returned to its source location.", picking.name))
            allowed = picking.location_dest_id._gw_get_responsible_users() | picking.gw_return_location_id._gw_get_responsible_users()
            if not (self.env.su or user.has_group('base.group_system') or not allowed or user in allowed):
                raise UserError(_("Only the persons in charge of the source or destination location can return %s.", picking.name))
            previous_dest = picking.location_dest_id
            picking.activity_unlink(['mail.mail_activity_data_todo'])
            picking.write({
                'location_dest_id': picking.gw_return_location_id.id,
                'gw_returned_to_source': True,
            })
            picking.move_line_ids.write({'location_dest_id': picking.gw_return_location_id.id})
            picking.message_post(body=_(
                "Goods not delivered to %(dest)s: returned to %(origin)s by %(user)s.",
                dest=previous_dest.display_name, origin=picking.gw_return_location_id.display_name, user=user.name))
            picking._gw_schedule_confirmation_activities()
        return True

    def action_cancel(self):
        if not self.env.context.get('gw_allow_cancel_confirmation') and any(
                p.gw_is_receipt_confirmation and p.state not in ('done', 'cancel') for p in self):
            raise UserError(_(
                "A receipt confirmation cannot be cancelled: the goods are in transit. "
                "Validate the quantities received, or use 'Return to Source' for goods that will not be delivered."))
        return super().action_cancel()

    @api.ondelete(at_uninstall=False)
    def _gw_unlink_except_pending_confirmation(self):
        if any(p.gw_is_receipt_confirmation and p.state not in ('done', 'cancel') for p in self):
            raise UserError(_("A pending receipt confirmation cannot be deleted: the goods are in transit."))

    def action_gw_view_receipt_confirmations(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action['domain'] = [('id', 'in', self.gw_receipt_picking_ids.ids)]
        action['context'] = {'create': False}
        if len(self.gw_receipt_picking_ids) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.gw_receipt_picking_ids.id
        return action
