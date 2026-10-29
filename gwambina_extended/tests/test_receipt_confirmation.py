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
        self.assertIs(res, True)
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
