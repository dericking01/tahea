from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestReceiptConfirmation(GwStockCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_a = cls.env['stock.location'].create({'name': 'Store A', 'location_id': cls.stock_location.id})
        cls.location_b = cls.env['stock.location'].create({
            'name': 'Store B',
            'location_id': cls.stock_location.id,
            'gw_responsible_user_ids': [(6, 0, cls.receiver_user.ids)],
        })
        cls.bin_b = cls.env['stock.location'].create({'name': 'Bin B1', 'location_id': cls.location_b.id})
        cls.int_type = cls.warehouse.int_type_id

    def _dispatch(self, lines, dest=None):
        for product, qty in lines:
            self._set_qty(product, self.location_a, qty)
        picking = self._create_picking(self.int_type, self.location_a, dest or self.location_b, lines, user=self.stock_user)
        picking.action_assign()
        return picking.with_user(self.stock_user)

    def test_flag_set_on_warehouse_internal_type(self):
        self.assertTrue(self.int_type.gw_receipt_confirmation)
        self.assertFalse(self.warehouse.in_type_id.gw_receipt_confirmation)
        self.assertEqual(self.bin_b._gw_get_responsible_users(), self.receiver_user)

    def test_full_flow_partial_receipt_backorder_and_return(self):
        picking = self._dispatch([(self.product_a, 10), (self.product_b, 4)])
        picking.button_validate()

        # Sender side: stock left A and sits in transit, B not yet increased
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.location_dest_id, self.transit_location)
        self.assertEqual(picking.gw_final_location_id, self.location_b)
        self.assertEqual(self._on_hand(self.product_a, self.location_a), 0)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 10)
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 0)

        receipt = picking.gw_receipt_picking_ids
        self.assertEqual(len(receipt), 1)
        self.assertTrue(receipt.gw_is_receipt_confirmation)
        self.assertEqual(receipt.location_id, self.transit_location)
        self.assertEqual(receipt.location_dest_id, self.location_b)
        self.assertEqual(receipt.gw_return_location_id, self.location_a)
        self.assertEqual(receipt.state, 'assigned')
        self.assertEqual(receipt.activity_ids.user_id, self.receiver_user)
        rc_type = self.warehouse.gw_receipt_confirm_type_id
        self.assertEqual(receipt.picking_type_id, rc_type)
        self.assertTrue(receipt.name.startswith('%s/RC/' % self.warehouse.code))
        self.assertEqual(rc_type.count_picking_ready, 1)

        # Only the person in charge of B can confirm
        with self.assertRaises(UserError):
            receipt.with_user(self.other_user).button_validate()
        # ...and the goods in transit cannot be cancelled
        with self.assertRaises(UserError):
            receipt.with_user(self.receiver_user).action_cancel()

        # Receiver: only 7 A and 4 B physically arrived -> backorder for 3 A, no wizard
        receipt_b = receipt.with_user(self.receiver_user)
        receipt_b.move_ids.filtered(lambda m: m.product_id == self.product_a).quantity = 7
        res = receipt_b.button_validate()
        # Standard backorder wizard, adapted to goods in transit
        self.assertEqual(res['res_model'], 'stock.backorder.confirmation')
        wizard = Form.from_action(self.env(user=self.receiver_user), res).save()
        self.assertTrue(wizard.gw_has_receipt_confirmation)
        self.assertTrue(wizard.gw_can_return_remaining)
        wizard.process()
        self.assertEqual(receipt.state, 'done')
        self.assertFalse(receipt.activity_ids)
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 7)
        self.assertEqual(self._on_hand(self.product_b, self.location_b), 4)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 3)

        backorder = self.env['stock.picking'].search([('backorder_id', '=', receipt.id)])
        self.assertEqual(len(backorder), 1)
        self.assertTrue(backorder.gw_is_receipt_confirmation)
        self.assertEqual(backorder.gw_dispatch_picking_id, picking)
        self.assertEqual(backorder.move_ids.product_uom_qty, 3)
        self.assertEqual(backorder.activity_ids.user_id, self.receiver_user)
        self.assertEqual(picking.gw_receipt_picking_count, 2)

        # Remaining goods will never arrive: return them to A
        with self.assertRaises(UserError):
            backorder.with_user(self.other_user).action_gw_return_to_source()
        backorder.with_user(self.receiver_user).action_gw_return_to_source()
        self.assertEqual(backorder.location_dest_id, self.location_a)
        self.assertTrue(backorder.gw_returned_to_source)
        # A has no person in charge: any stock user can receive them back
        backorder.with_user(self.other_user).button_validate()
        self.assertEqual(backorder.state, 'done')
        self.assertEqual(self._on_hand(self.product_a, self.location_a), 3)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 0)

    def test_sender_partial_dispatch_backorder_keeps_real_destination(self):
        picking = self._dispatch([(self.product_a, 10)])
        picking.move_ids.quantity = 6
        res = picking.button_validate()
        Form.from_action(self.env, res).save().process()
        sender_backorder = self.env['stock.picking'].search([('backorder_id', '=', picking.id)])
        self.assertEqual(sender_backorder.location_dest_id, self.location_b)
        self.assertEqual(sender_backorder.move_ids.location_dest_id, self.location_b)
        self.assertFalse(sender_backorder.gw_is_receipt_confirmation)
        self.assertEqual(picking.gw_receipt_picking_ids.move_ids.product_uom_qty, 6)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 6)

        # The sender backorder goes through the same confirmation flow
        sender_backorder.with_user(self.stock_user).button_validate()
        self.assertEqual(len(sender_backorder.gw_receipt_picking_ids), 1)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 10)

    def test_destination_sublocation_uses_parent_responsible(self):
        picking = self._dispatch([(self.product_a, 2)], dest=self.bin_b)
        picking.button_validate()
        receipt = picking.gw_receipt_picking_ids
        self.assertEqual(receipt.location_dest_id, self.bin_b)
        with self.assertRaises(UserError):
            receipt.with_user(self.stock_user).button_validate()
        receipt.with_user(self.receiver_user).button_validate()
        self.assertEqual(self._on_hand(self.product_a, self.bin_b), 2)

    def test_admin_can_confirm(self):
        picking = self._dispatch([(self.product_a, 2)])
        picking.button_validate()
        picking.gw_receipt_picking_ids.with_user(self.admin_user).button_validate()
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 2)

    def test_no_person_in_charge_means_direct_transfer(self):
        location_c = self.env['stock.location'].create({'name': 'Store C', 'location_id': self.stock_location.id})
        picking = self._dispatch([(self.product_a, 5)], dest=location_c)
        picking.button_validate()
        self.assertEqual(picking.location_dest_id, location_c)
        self.assertFalse(picking.gw_receipt_picking_ids)
        self.assertEqual(self._on_hand(self.product_a, location_c), 5)

    def test_feature_disabled_on_operation_type(self):
        self.int_type.gw_receipt_confirmation = False
        picking = self._dispatch([(self.product_a, 5)])
        picking.button_validate()
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 5)
        self.assertFalse(picking.gw_receipt_picking_ids)

    def test_dispatch_checks_source_stock(self):
        picking = self._dispatch([(self.product_a, 2)])
        picking.move_ids.quantity = 5
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_new_warehouse_internal_type_flagged(self):
        wh2 = self.env['stock.warehouse'].create({'name': 'GW Second WH', 'code': 'GW2', 'company_id': self.company.id})
        self.assertTrue(wh2.int_type_id.gw_receipt_confirmation)

    def test_overview_shows_receipts_and_receipt_confirmations(self):
        rc_type = self.warehouse.gw_receipt_confirm_type_id
        self.assertTrue(rc_type.active)
        self.assertEqual(rc_type.code, 'internal')
        self.assertEqual(rc_type.default_location_src_id, self.transit_location)
        # Overview (stock.picking.type kanban), also for a location-restricted user of this warehouse
        self.stock_user.write({
            'restrict_stock_locations': True,
            'allowed_stock_location_ids': [(6, 0, self.warehouse.view_location_id.ids)],
        })
        for user in (self.stock_user, self.receiver_user):
            cards = self.env['stock.picking.type'].with_user(user).web_search_read(
                [('warehouse_id', '=', self.warehouse.id)], {'id': {}})['records']
            ids = {c['id'] for c in cards}
            self.assertIn(self.warehouse.in_type_id.id, ids)
            self.assertIn(rc_type.id, ids)

    def test_new_warehouse_gets_receipt_confirmation_type(self):
        wh2 = self.env['stock.warehouse'].create({'name': 'GW Third WH', 'code': 'GW3', 'company_id': self.company.id})
        self.assertTrue(wh2.gw_receipt_confirm_type_id)
        self.assertEqual(wh2.gw_receipt_confirm_type_id.warehouse_id, wh2)

    def test_initiator_cannot_receive_own_transfer(self):
        # The receiver initiates a transfer to his own location: he cannot confirm it himself
        self._set_qty(self.product_a, self.location_a, 4)
        picking = self._create_picking(self.int_type, self.location_a, self.location_b, [(self.product_a, 4)],
                                       user=self.receiver_user).with_user(self.receiver_user)
        picking.action_assign()
        picking.button_validate()
        receipt = picking.gw_receipt_picking_ids
        self.assertEqual(receipt.gw_dispatched_by_id, self.receiver_user)
        with self.assertRaises(UserError) as err:
            receipt.with_user(self.receiver_user).button_validate()
        self.assertIn('initiated', str(err.exception))
        # A second person in charge of B can; so can an administrator
        self.location_b.gw_responsible_user_ids = [(4, self.other_user.id)]
        receipt.with_user(self.other_user).button_validate()
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 4)

    def test_dispatcher_cannot_receive_even_if_not_creator(self):
        self._set_qty(self.product_a, self.location_a, 2)
        picking = self._create_picking(self.int_type, self.location_a, self.location_b, [(self.product_a, 2)])
        picking.action_assign()
        picking.with_user(self.receiver_user).button_validate()  # receiver dispatched it
        receipt = picking.gw_receipt_picking_ids
        with self.assertRaises(UserError):
            receipt.with_user(self.receiver_user).button_validate()
        receipt.with_user(self.admin_user).button_validate()
        self.assertEqual(receipt.state, 'done')

    def test_no_backorder_returns_remaining_to_source(self):
        picking = self._dispatch([(self.product_a, 10)])
        picking.button_validate()
        receipt = picking.gw_receipt_picking_ids.with_user(self.receiver_user)
        receipt.move_ids.quantity = 6
        res = receipt.button_validate()
        Form.from_action(self.env(user=self.receiver_user), res).save().process_cancel_backorder()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(self._on_hand(self.product_a, self.location_b), 6)
        backorder = receipt.backorder_ids
        self.assertEqual(len(backorder), 1)
        self.assertEqual(receipt.gw_backorder_count, 1)
        self.assertTrue(backorder.gw_returned_to_source)
        self.assertEqual(backorder.location_dest_id, self.location_a)
        self.assertEqual(backorder.move_ids.product_uom_qty, 4)
        # Received back at A (no person in charge there: any stock user, even the initiator)
        backorder.with_user(self.stock_user).button_validate()
        self.assertEqual(self._on_hand(self.product_a, self.location_a), 4)
        self.assertEqual(self._on_hand(self.product_a, self.transit_location), 0)

    def test_returned_goods_partial_backorder_no_return_option(self):
        picking = self._dispatch([(self.product_a, 5)])
        picking.button_validate()
        receipt = picking.gw_receipt_picking_ids
        receipt.with_user(self.receiver_user).action_gw_return_to_source()
        receipt.move_ids.quantity = 3
        res = receipt.with_user(self.other_user).button_validate()
        wizard = Form.from_action(self.env(user=self.other_user), res).save()
        self.assertFalse(wizard.gw_can_return_remaining)
        wizard.process_cancel_backorder()
        # Goods in transit are never dropped: the remainder stays expected at the source
        self.assertEqual(receipt.backorder_ids.move_ids.product_uom_qty, 2)
        self.assertEqual(receipt.backorder_ids.location_dest_id, self.location_a)

    def test_admin_initiator_cannot_receive_own_transfer(self):
        self.location_b.gw_responsible_user_ids = [(4, self.admin_user.id)]
        self._set_qty(self.product_a, self.location_a, 3)
        picking = self._create_picking(self.int_type, self.location_a, self.location_b, [(self.product_a, 3)],
                                       user=self.admin_user).with_user(self.admin_user)
        picking.action_assign()
        picking.button_validate()
        receipt = picking.gw_receipt_picking_ids
        # Admin initiated it: "Pending Validation" instead of "Validate", and validation refused
        self.assertTrue(receipt.with_user(self.admin_user).gw_pending_validation)
        self.assertFalse(receipt.with_user(self.receiver_user).gw_pending_validation)
        action = receipt.with_user(self.admin_user).action_gw_pending_validation()
        self.assertEqual(action['tag'], 'display_notification')
        with self.assertRaises(UserError):
            receipt.with_user(self.admin_user).button_validate()
        receipt.with_user(self.receiver_user).button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertFalse(receipt.with_user(self.admin_user).gw_pending_validation)
