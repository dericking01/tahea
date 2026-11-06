from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .common import IntercompanyTransferCommon


@tagged('post_install', '-at_install', 'intercompany_stock_transfer')
class TestIntercompanyTransferWorkflow(IntercompanyTransferCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_stock(cls.product_1, cls.loc_a1, 20)
        cls._add_stock(cls.product_2, cls.shelf_a1, 15)

    # 1 / 12
    def test_01_authorized_user_creates_and_confirms(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        self.assertTrue(transfer.name.startswith('ICT/'))
        self.assertEqual(transfer.state, 'draft')
        self.assertFalse(transfer.picking_ids, "Nothing is generated before confirmation")

        transfer.action_confirm()
        self.assertEqual(transfer.state, 'confirmed')
        self.assertEqual(transfer.confirm_user_id, self.user_ict)
        dispatch = transfer.picking_ids
        self.assertEqual(len(dispatch), 1)
        self.assertEqual(dispatch.intercompany_role, 'dispatch')
        self.assertEqual(dispatch.company_id, self.company_a)
        self.assertEqual(dispatch.picking_type_id, self.wh_a1.out_type_id)
        self.assertEqual(dispatch.location_id, self.loc_a1)
        self.assertEqual(dispatch.location_dest_id, self.transit)
        self.assertEqual(dispatch.move_ids.company_id, self.company_a)
        self.assertEqual(dispatch.state, 'assigned')
        self.assertEqual(transfer.line_ids.qty_reserved, 5)
        self.assertEqual(transfer.line_ids.source_qty_available, 15, "20 on hand - 5 reserved")
        # Confirmation alone never moves stock nor creates the receipt.
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)
        self.assertFalse(transfer._get_pickings('receipt'))

    # 4 / 5 / 6
    def test_04_field_domains_follow_companies_and_warehouses(self):
        Transfer = self.env['intercompany.stock.transfer']

        def domain_result(field, comodel, **ctx):
            return self.env[comodel].search(safe_eval(Transfer._fields[field].domain, ctx))

        src_wh = domain_result('source_warehouse_id', 'stock.warehouse',
                               source_parent_company_id=self.company_a.id, source_branch_id=False)
        self.assertEqual(src_wh, self.wh_a1 | self.wh_a2 | self.wh_branch_a,
                         "a company shows its own and its branches' warehouses")
        branch_wh = domain_result('source_warehouse_id', 'stock.warehouse',
                                  source_parent_company_id=self.company_a.id, source_branch_id=self.branch_a.id)
        self.assertEqual(branch_wh, self.wh_branch_a)
        dst_wh = domain_result('dest_warehouse_id', 'stock.warehouse',
                               dest_parent_company_id=self.company_b.id, dest_branch_id=False)
        self.assertEqual(dst_wh, self.wh_b1 | self.wh_b2)

        src_locs = domain_result('source_location_id', 'stock.location', source_warehouse_id=self.wh_a1.id)
        self.assertIn(self.loc_a1, src_locs)
        self.assertIn(self.shelf_a1, src_locs, "nested child locations are eligible")
        self.assertTrue(all(loc.usage == 'internal' for loc in src_locs))
        self.assertFalse(src_locs & self.wh_a2.view_location_id.child_ids)
        self.assertNotIn(self.transit, src_locs)
        dst_locs = domain_result('dest_location_id', 'stock.location', dest_warehouse_id=self.wh_b1.id)
        self.assertIn(self.shelf_b1, dst_locs)
        self.assertFalse(dst_locs.filtered(lambda l: l.company_id != self.company_b))

    def test_05_onchange_clears_incompatible_selection(self):
        form = Form(self._as(self.user_ict, self.env['intercompany.stock.transfer']))
        form.source_parent_company_id = self.company_a
        form.source_warehouse_id = self.wh_a2
        self.assertEqual(form.source_location_id, self.wh_a2.lot_stock_id)
        form.dest_parent_company_id = self.company_b
        form.dest_warehouse_id = self.wh_b1
        form.dest_location_id = self.shelf_b1
        # Switching the destination warehouse drops the incompatible location.
        form.dest_warehouse_id = self.wh_b2
        self.assertEqual(form.dest_location_id, self.wh_b2.lot_stock_id)
        # Switching the company drops the warehouse (B has several: no guess).
        form.source_parent_company_id = self.company_b
        self.assertFalse(form.source_warehouse_id)
        self.assertFalse(form.source_location_id)

    # 7
    def test_07_invalid_combinations_rejected_server_side(self):
        cases = [
            {'source_warehouse_id': self.wh_b1.id},                      # warehouse of another company
            {'source_location_id': self.wh_a2.lot_stock_id.id},          # location of another warehouse
            {'dest_location_id': self.loc_a1.id},                        # destination location of company A
            {'dest_location_id': self.wh_b1.view_location_id.id},        # view location
            {'dest_location_id': self.transit.id},                       # transit location
            {'dest_company_id': self.company_a.id,                        # same company
             'dest_warehouse_id': self.wh_a2.id, 'dest_location_id': self.wh_a2.lot_stock_id.id},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValidationError), self.cr.savepoint():
                self._create_transfer([(self.product_1, 1)], **values)
        # Same rules apply on write (draft) through the ORM/RPC.
        transfer = self._create_transfer([(self.product_1, 1)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            transfer.write({'dest_location_id': self.loc_a1.id})

    def test_07b_invalid_lines_rejected(self):
        for product, qty in ((self.product_1, 0), (self.product_1, -3), (self.product_consu, 1),
                             (self.product_a_only, 1)):
            with self.subTest(product=product.name, qty=qty), self.assertRaises(ValidationError), \
                    self.cr.savepoint():
                self._create_transfer([(product, qty)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._create_transfer([(self.product_1, 1, {'product_uom_id': self.env.ref('uom.product_uom_kgm').id})])

    def test_07c_structure_frozen_after_confirmation(self):
        transfer = self._create_transfer([(self.product_1, 2)])
        transfer.action_confirm()
        with self.assertRaises(UserError):
            transfer.write({'dest_location_id': self.shelf_b1.id})
        with self.assertRaises(UserError):
            transfer.line_ids.write({'product_uom_qty': 10})
        with self.assertRaises(UserError):
            transfer.write({'line_ids': [Command.create({'product_id': self.product_2.id, 'product_uom_qty': 1})]})

    # 8 / 10 / 11 / 12
    def test_08_full_flow_multiple_lines(self):
        transfer = self._create_transfer(
            [(self.product_1, 6), (self.product_2, 4)],
            source_location_id=self.loc_a1.id, dest_location_id=self.shelf_b1.id)
        transfer.action_confirm()
        transfer.action_dispatch()
        self.assertEqual(transfer.state, 'in_transit')
        self.assertEqual(transfer.dispatch_user_id, self.user_ict)
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 14)
        self.assertEqual(self._on_hand(self.product_2, self.shelf_a1), 11, "taken from the child location")
        # In transit: out of A, not yet in B.
        self.assertEqual(self._on_hand(self.product_1, self.transit), 6)
        self.assertEqual(self._on_hand(self.product_1, self.wh_b1.view_location_id), 0)
        self.assertEqual(transfer.line_ids.mapped('qty_in_transit'), [6, 4])

        receipt = transfer._get_pickings('receipt')
        self.assertEqual(len(receipt), 1)
        self.assertEqual(receipt.company_id, self.company_b)
        self.assertEqual(receipt.move_ids.company_id, self.company_b)
        self.assertEqual(receipt.picking_type_id, self.wh_b1.in_type_id)
        self.assertEqual(receipt.location_id, self.transit)
        self.assertEqual(receipt.location_dest_id, self.shelf_b1)
        self.assertEqual(receipt.state, 'assigned')
        self.assertEqual(receipt.move_ids.move_orig_ids, transfer._get_pickings('dispatch').move_ids,
                         "receipt moves are chained to the dispatch moves (traceability)")

        transfer.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(transfer.receive_user_id, self.user_ict)
        self.assertEqual(self._on_hand(self.product_1, self.shelf_b1), 6)
        self.assertEqual(self._on_hand(self.product_2, self.shelf_b1), 4)
        self.assertEqual(self._on_hand(self.product_1, self.transit), 0)
        self.assertEqual(transfer.line_ids.mapped('qty_received'), [6, 4])
        self.assertEqual(transfer.line_ids.mapped('qty_in_transit'), [0, 0])

    def test_08b_uom_conversion(self):
        self._add_stock(self.product_2, self.loc_a1, 30)
        transfer = self._create_transfer([(self.product_2, 2, {'product_uom_id': self.uom_dozen.id})])
        transfer.action_confirm()
        transfer.action_dispatch()
        transfer.action_receive()
        self.assertEqual(self._on_hand(self.product_2, self.loc_b1), 24)
        self.assertEqual(transfer.line_ids.qty_received, 2)

    # 9
    def test_09_insufficient_stock_prevents_dispatch(self):
        transfer = self._create_transfer([(self.product_1, 25)])
        transfer.action_confirm()
        move = transfer._get_pickings('dispatch').move_ids
        self.assertEqual(move.quantity, 20, "only the available quantity is reserved")
        self._set_quantity(move, 25)
        with self.assertRaises(UserError) as error:
            transfer.action_dispatch()
        self.assertIn('Not enough stock', str(error.exception))
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)

    def test_09b_respects_other_reservations(self):
        other = self.env['stock.picking'].with_company(self.company_a).create({
            'company_id': self.company_a.id,
            'picking_type_id': self.wh_a1.out_type_id.id,
            'location_id': self.loc_a1.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [Command.create({
                'name': 'other', 'product_id': self.product_1.id, 'product_uom_qty': 18,
                'location_id': self.loc_a1.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id})],
        })
        other.action_confirm()
        other.action_assign()
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        move = transfer._get_pickings('dispatch').move_ids
        self.assertEqual(move.quantity, 2)
        self.assertEqual(transfer.line_ids.source_qty_available, 0)
        self._set_quantity(move, 5)
        with self.assertRaises(UserError) as error:
            transfer.action_dispatch()
        self.assertIn('reservations of other operations', str(error.exception))
        self.assertEqual(other.move_ids.quantity, 18, "the other reservation is untouched")

    # 13
    def test_13_lot_and_serial_tracking(self):
        self._add_stock(self.product_lot, self.loc_a1, 5, lot=self.lot_1)
        self._add_stock(self.product_lot, self.loc_a1, 5, lot=self.lot_2)
        for serial in self.serials:
            self._add_stock(self.product_serial, self.loc_a1, 1, lot=serial)
        transfer = self._create_transfer([
            (self.product_lot, 3, {'lot_id': self.lot_2.id}),
            (self.product_serial, 2),
        ])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        lot_move = dispatch.move_ids.filtered(lambda m: m.product_id == self.product_lot)
        self.assertEqual(lot_move.move_line_ids.lot_id, self.lot_2, "requested lot is reserved")
        transfer.action_dispatch()
        sent_serials = dispatch.move_ids.filtered(
            lambda m: m.product_id == self.product_serial).move_line_ids.lot_id
        self.assertEqual(len(sent_serials), 2)

        receipt = transfer._get_pickings('receipt')
        self.assertEqual(receipt.move_line_ids.filtered(
            lambda ml: ml.product_id == self.product_lot).lot_id, self.lot_2)
        self.assertEqual(receipt.move_line_ids.filtered(
            lambda ml: ml.product_id == self.product_serial).lot_id, sent_serials)
        transfer.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(self._on_hand(self.product_lot, self.loc_b1, self.lot_2), 3)
        self.assertEqual(self._on_hand(self.product_lot, self.loc_a1, self.lot_2), 2)
        for serial in sent_serials:
            self.assertEqual(self._on_hand(self.product_serial, self.loc_b1, serial), 1)
            self.assertEqual(self._on_hand(self.product_serial, self.loc_a1, serial), 0)
        self.assertIn('LOT-002', transfer.line_ids[0].lot_names)

    def test_13b_cannot_receive_a_lot_that_was_not_dispatched(self):
        self._add_stock(self.product_lot, self.loc_a1, 5, lot=self.lot_1)
        transfer = self._create_transfer([(self.product_lot, 2)])
        transfer.action_confirm()
        transfer.action_dispatch()
        receipt = transfer._get_pickings('receipt')
        receipt.move_line_ids.lot_id = self.lot_2
        with self.assertRaises(ValidationError) as error:
            transfer.action_receive()
        self.assertIn('LOT-002', str(error.exception))

    # 14
    def test_14_partial_dispatch_and_receipt_with_backorders(self):
        transfer = self._create_transfer([(self.product_1, 10)])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        self._set_quantity(dispatch.move_ids, 6)
        self._validate(self._as(self.user_ict, dispatch), backorder=True)
        self.assertEqual(transfer.state, 'in_transit')
        backorder = transfer._get_pickings('dispatch', open_only=True)
        self.assertEqual(len(backorder), 1, "native backorder linked to the transfer")
        self.assertEqual(backorder.backorder_id, dispatch)
        self.assertEqual(backorder.move_ids.product_uom_qty, 4)
        self.assertEqual(transfer.line_ids.qty_dispatched, 6)

        receipt = transfer._get_pickings('receipt')
        self.assertEqual(receipt.move_ids.product_uom_qty, 6, "receipt mirrors what was dispatched")
        self._set_quantity(receipt.move_ids, 4)
        self._validate(self._as(self.user_ict, receipt), backorder=True)
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 4)
        self.assertEqual(transfer.line_ids.qty_received, 4)
        self.assertEqual(transfer.line_ids.qty_in_transit, 2)
        receipt_bo = transfer._get_pickings('receipt', open_only=True)
        self.assertEqual(receipt_bo.move_ids.product_uom_qty, 2)

        transfer.action_dispatch()  # the 4 remaining units
        self.assertEqual(len(transfer._get_pickings('receipt', open_only=True)), 2)
        self.assertEqual(transfer.line_ids.qty_in_transit, 6)
        for receipt in transfer._get_pickings('receipt', open_only=True):
            self._validate(self._as(self.user_ict, receipt))
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 10)
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 10)

    def test_14b_declined_backorders(self):
        transfer = self._create_transfer([(self.product_1, 10)])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        self._set_quantity(dispatch.move_ids, 7)
        self._validate(self._as(self.user_ict, dispatch), backorder=False)
        self.assertFalse(transfer._get_pickings('dispatch', open_only=True))
        receipt = transfer._get_pickings('receipt')
        self._set_quantity(receipt.move_ids, 5)
        self._validate(self._as(self.user_ict, receipt), backorder=False)
        # 2 units are stranded in transit: still tracked, and receivable later.
        self.assertEqual(transfer.state, 'in_transit')
        self.assertEqual(transfer.line_ids.qty_in_transit, 2)
        self.assertTrue(transfer.can_receive)
        transfer.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 7)
        self.assertEqual(self._on_hand(self.product_1, self.transit), 0)

    def test_14c_multi_step_reception_reaches_selected_location(self):
        self.wh_b2.reception_steps = 'two_steps'
        shelf = self.env['stock.location'].create({
            'name': 'Shelf B2', 'location_id': self.wh_b2.lot_stock_id.id, 'usage': 'internal',
            'company_id': self.company_b.id})
        transfer = self._create_transfer([(self.product_1, 3)], dest_warehouse_id=self.wh_b2.id,
                                         dest_location_id=shelf.id)
        transfer.action_confirm()
        transfer.action_dispatch()
        receipt = transfer._get_pickings('receipt')
        self.assertEqual(receipt.location_dest_id, self.wh_b2.wh_input_stock_loc_id)
        transfer.action_receive()
        self.assertEqual(transfer.state, 'received')
        internal = receipt.move_ids.move_dest_ids
        self.assertTrue(internal, "native push rule created the input -> stock step")
        self.assertEqual(internal.location_final_id | internal.location_dest_id, shelf)
        internal.picking_id.button_validate()
        self.assertEqual(self._on_hand(self.product_1, shelf), 3)

    # 15
    def test_15_cancel_before_dispatch(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        transfer._action_cancel('Not needed anymore')
        self.assertEqual(transfer.state, 'cancel')
        self.assertEqual(transfer.cancel_reason, 'Not needed anymore')
        self.assertEqual(transfer.cancel_user_id, self.user_ict)
        self.assertEqual(dispatch.state, 'cancel')
        self.assertFalse(transfer._get_pickings('return'))
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)
        self.assertTrue(dispatch.exists(), "operations are kept for traceability")
        with self.assertRaises(UserError):
            transfer._action_cancel('again')
        with self.assertRaises(UserError):
            dispatch.unlink()

    def test_15b_cancel_after_dispatch_creates_return(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        transfer.action_dispatch()
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 15)
        wizard = self._as(self.user_ict, self.env['intercompany.stock.transfer.cancel']).create({
            'transfer_ids': [Command.set(transfer.ids)], 'reason': 'Truck broke down'})
        self.assertTrue(wizard.has_dispatched_stock)
        wizard.action_cancel()
        self.assertEqual(transfer.state, 'cancel')
        self.assertEqual(transfer._get_pickings('receipt').state, 'cancel')
        ret = transfer._get_pickings('return')
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret.company_id, self.company_a)
        self.assertEqual(ret.location_id, self.transit)
        self.assertEqual(ret.location_dest_id, self.loc_a1)
        # Nothing reversed silently: stock is still in transit until validated.
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 15)
        self._validate(self._as(self.user_ict, ret))
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)
        self.assertEqual(self._on_hand(self.product_1, self.transit), 0)
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 0)
        self.assertEqual(transfer.state, 'cancel')
        done_moves = self.env['stock.move'].search(
            [('intercompany_line_id', '=', transfer.line_ids.id), ('state', '=', 'done')])
        self.assertEqual(len(done_moves), 2, "exactly one dispatch and one return")

    def test_15c_cannot_dispatch_cancelled_transfer(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        transfer._action_cancel('x')
        with self.assertRaises(UserError):
            transfer.action_dispatch()

    # 16
    def test_16_repeated_actions_are_idempotent(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        transfer.action_confirm()
        self.assertEqual(len(transfer.picking_ids), 1)

        transfer.action_dispatch()
        with self.assertRaises(UserError):
            transfer.action_dispatch()
        dispatch = transfer._get_pickings('dispatch')
        # Re-running the receipt generation does not duplicate it.
        transfer._create_receipt_for_dispatch(dispatch)
        transfer._ict_after_pickings_done(dispatch)
        self.assertEqual(len(transfer._get_pickings('receipt')), 1)
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 15)

        transfer.action_receive()
        with self.assertRaises(UserError):
            transfer.action_receive()
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 5)

    def test_16b_over_receipt_and_over_dispatch_blocked(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        self._set_quantity(dispatch.move_ids, 8)
        with self.assertRaises(ValidationError) as error:
            transfer.action_dispatch()
        self.assertIn('more than the requested quantity', str(error.exception))
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)
        self._set_quantity(dispatch.move_ids, 5)
        transfer.action_dispatch()
        receipt = transfer._get_pickings('receipt')
        self._set_quantity(receipt.move_ids, 9)
        with self.assertRaises(ValidationError) as error:
            transfer.action_receive()
        self.assertIn('still in transit', str(error.exception))
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 0)

    def test_16c_duplicated_operation_cannot_double_deduct(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        transfer.action_dispatch()
        dispatch = transfer._get_pickings('dispatch')
        copy = dispatch.copy()
        copy.action_confirm()
        copy.action_assign()
        with self.assertRaises(ValidationError) as error:
            self._validate(self._as(self.user_ict, copy))
        self.assertIn('more than the requested quantity', str(error.exception))
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 15)

    def test_17_native_return_from_destination(self):
        transfer = self._create_transfer([(self.product_1, 5)])
        transfer.action_confirm()
        transfer.action_dispatch()
        transfer.action_receive()
        receipt = transfer._get_pickings('receipt')
        wizard = Form(self.env['stock.return.picking'].with_context(
            active_id=receipt.id, active_model='stock.picking')).save()
        wizard.product_return_moves.quantity = 2
        ret = wizard._create_return()
        self.assertEqual(ret.intercompany_role, 'dest_return')
        self._validate(self._as(self.user_ict, ret))
        self.assertEqual(transfer.line_ids.qty_received, 3)
        self.assertEqual(transfer.line_ids.qty_in_transit, 2)
        self.assertEqual(transfer.state, 'in_transit')


@tagged('post_install', '-at_install', 'intercompany_stock_transfer')
class TestIntercompanyTransferBranches(IntercompanyTransferCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.branch_stock = cls.wh_branch_a.lot_stock_id
        cls._add_stock(cls.product_1, cls.branch_stock, 10)
        cls._add_stock(cls.product_1, cls.loc_a1, 10)

    def test_new_form_lists_all_user_companies(self):
        """Regression: the company dropdowns were empty on a new transfer."""
        Transfer = self.env['intercompany.stock.transfer'].with_user(self.user_ict).with_context(
            allowed_company_ids=self.company_a.ids)  # only one company ticked in the switcher
        values = Transfer.onchange({}, [], {
            'allowed_company_ids': {}, 'allowed_parent_company_ids': {},
            'source_company_id': {}, 'source_parent_company_id': {}, 'source_has_branches': {},
        })['value']
        self.assertEqual(set(values['allowed_company_ids']),
                         set((self.company_a | self.company_b | self.branch_a).ids))
        self.assertEqual(set(values['allowed_parent_company_ids']), set((self.company_a | self.company_b).ids),
                         "branches are chosen in the Branch field, not as top-level companies")
        self.assertTrue(values['source_has_branches'])
        # What the dropdowns query, with the field context sent by the form:
        ctx = {'allowed_company_ids': values['allowed_company_ids']}
        warehouses = self.env['stock.warehouse'].with_user(self.user_ict).with_context(ctx).search(
            [('company_id', 'child_of', self.company_b.id)])
        self.assertEqual(warehouses, self.wh_b1 | self.wh_b2, "warehouses of a company not ticked in the switcher")
        locations = self.env['stock.location'].with_user(self.user_ict).with_context(ctx).search(
            [('usage', '=', 'internal'), ('warehouse_id', '=', self.wh_b1.id)])
        self.assertIn(self.shelf_b1, locations)

    def test_branch_dropdown_and_warehouse_selection(self):
        form = Form(self._as(self.user_ict, self.env['intercompany.stock.transfer'],
                             companies=self.company_a))
        form.source_parent_company_id = self.company_a
        self.assertTrue(form.source_has_branches)
        self.assertFalse(form.source_branch_id)
        # Picking a branch warehouse selects the branch automatically.
        form.source_warehouse_id = self.wh_branch_a
        self.assertEqual(form.source_branch_id, self.branch_a)
        self.assertEqual(form.source_company_id, self.branch_a)
        self.assertEqual(form.source_location_id, self.branch_stock)
        # Back to the main company: the branch warehouse is no longer compatible.
        form.source_branch_id = self.env['res.company']
        self.assertEqual(form.source_company_id, self.company_a)
        self.assertNotEqual(form.source_warehouse_id, self.wh_branch_a)
        # Choosing the branch explicitly proposes its single warehouse.
        form.source_branch_id = self.branch_a
        self.assertEqual(form.source_warehouse_id, self.wh_branch_a)
        form.dest_parent_company_id = self.company_b
        self.assertFalse(form.dest_has_branches)
        form.dest_warehouse_id = self.wh_b1
        with form.line_ids.new() as line:
            line.product_id = self.product_1
            line.product_uom_qty = 4
        transfer = form.save()
        self.assertEqual(transfer.source_company_id, self.branch_a)
        self.assertEqual(transfer.source_parent_company_id, self.company_a)

    def test_branch_to_company_full_flow_with_one_company_ticked(self):
        """Branch -> other company, while only the branch is active in the switcher."""
        transfer = self._create_transfer(
            [(self.product_1, 4)],
            source_company_id=self.branch_a.id, source_warehouse_id=self.wh_branch_a.id,
            source_location_id=self.branch_stock.id)
        self.assertEqual(transfer.source_parent_company_id, self.company_a)
        self.assertEqual(transfer.source_branch_id, self.branch_a)
        transfer = transfer.with_context(allowed_company_ids=self.branch_a.ids)
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        self.assertEqual(dispatch.company_id, self.branch_a)
        transfer.action_dispatch()
        receipt = transfer._get_pickings('receipt')
        self.assertEqual(receipt.company_id, self.company_b)
        transfer.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(self._on_hand(self.product_1, self.branch_stock), 6)
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 10, "parent company stock untouched")
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 4)

    def test_parent_to_own_branch(self):
        transfer = self._create_transfer(
            [(self.product_1, 3)], dest_parent_company_id=self.company_a.id, dest_branch_id=self.branch_a.id,
            dest_company_id=False, dest_warehouse_id=self.wh_branch_a.id, dest_location_id=self.branch_stock.id)
        self.assertEqual(transfer.dest_company_id, self.branch_a)
        transfer.action_confirm()
        transfer.action_dispatch()
        transfer.action_receive()
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 7)
        self.assertEqual(self._on_hand(self.product_1, self.branch_stock), 13)

    def test_inconsistent_branch_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_transfer([(self.product_1, 1)], source_parent_company_id=self.company_b.id,
                                  source_branch_id=self.branch_a.id)
        with self.assertRaises(ValidationError):
            self._create_transfer([(self.product_1, 1)], source_company_id=self.company_a.id,
                                  source_branch_id=self.branch_a.id)
