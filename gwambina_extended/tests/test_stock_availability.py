from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestStockAvailability(GwStockCommon):

    def test_delivery_lists_all_short_products(self):
        self._set_qty(self.product_a, self.stock_location, 5)
        self._set_qty(self.product_b, self.stock_location, 2)
        self._set_qty(self.product_d, self.stock_location, 50)
        delivery = self._create_picking(
            self.warehouse.out_type_id, self.stock_location, self.customer_location,
            [(self.product_a, 10), (self.product_b, 1), (self.product_c, 3), (self.product_d, 4)])
        quantities = {self.product_a: 10, self.product_b: 3, self.product_c: 3, self.product_d: 4}
        for move in delivery.move_ids:
            move.quantity = quantities[move.product_id]

        with self.assertRaises(UserError) as err:
            delivery.button_validate()
        message = str(err.exception)
        self.assertIn('3 product(s)', message)
        for name in ('GW Product A', 'GW Product B', 'GW Product C'):
            self.assertIn(name, message)
        self.assertNotIn('GW Product D', message)
        self.assertNotEqual(delivery.state, 'done')

    def test_delivery_with_enough_stock_validates(self):
        self._set_qty(self.product_a, self.stock_location, 5)
        self._set_qty(self.product_b, self.stock_location, 5)
        delivery = self._create_picking(
            self.warehouse.out_type_id, self.stock_location, self.customer_location,
            [(self.product_a, 5), (self.product_b, 2)])
        delivery.action_assign()
        delivery.button_validate()
        self.assertEqual(delivery.state, 'done')
        self.assertEqual(self._on_hand(self.product_a, self.stock_location), 0)

    def test_partial_delivery_only_checks_processed_quantities(self):
        self._set_qty(self.product_a, self.stock_location, 3)
        delivery = self._create_picking(
            self.warehouse.out_type_id, self.stock_location, self.customer_location, [(self.product_a, 10)])
        delivery.action_assign()
        self.assertEqual(delivery.move_ids.quantity, 3)
        res = delivery.button_validate()
        self.assertEqual(res.get('res_model'), 'stock.backorder.confirmation')

    def test_internal_transfer_lists_all_short_products(self):
        shelf = self.env['stock.location'].create({'name': 'Shelf X', 'location_id': self.stock_location.id})
        self._set_qty(self.product_a, self.stock_location, 1)
        internal = self._create_picking(
            self.warehouse.int_type_id, self.stock_location, shelf,
            [(self.product_a, 4), (self.product_b, 2)])
        for move in internal.move_ids:
            move.quantity = move.product_uom_qty
        with self.assertRaises(UserError) as err:
            internal.button_validate()
        self.assertIn('GW Product A', str(err.exception))
        self.assertIn('GW Product B', str(err.exception))

    def test_receipts_and_consumables_not_checked(self):
        consumable = self.env['product.product'].create({'name': 'GW Consumable', 'is_storable': False, 'type': 'consu'})
        delivery = self._create_picking(
            self.warehouse.out_type_id, self.stock_location, self.customer_location, [(consumable, 5)])
        delivery.move_ids.quantity = 5
        delivery.button_validate()
        self.assertEqual(delivery.state, 'done')

        receipt = self._create_picking(
            self.warehouse.in_type_id, self.supplier_location, self.stock_location, [(self.product_a, 5)])
        receipt.move_ids.quantity = 5
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
