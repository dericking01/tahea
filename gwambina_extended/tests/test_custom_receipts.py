from odoo.tests import tagged

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestCustomReceipts(GwStockCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Location = cls.env['stock.location']
        cls.loc_a = Location.create({'name': 'Store A', 'location_id': cls.stock_location.id})
        cls.loc_b = Location.create({'name': 'Store B', 'location_id': cls.stock_location.id})
        cls.loc_b_bin = Location.create({'name': 'Bin B1', 'location_id': cls.loc_b.id})
        cls.loc_c = Location.create({'name': 'Store C', 'location_id': cls.stock_location.id})

        def picking_type(name, code, dest, seq_code):
            return cls.env['stock.picking.type'].create({
                'name': name,
                'code': code,
                'sequence_code': seq_code,
                'warehouse_id': cls.warehouse.id,
                'company_id': cls.company.id,
                'default_location_src_id': cls.supplier_location.id if code == 'incoming' else cls.stock_location.id,
                'default_location_dest_id': dest.id,
            })

        cls.type_a = picking_type('Receipt Store A', 'incoming', cls.loc_a, 'GRA')
        cls.type_b = picking_type('Receipt Store B', 'internal', cls.loc_b_bin, 'GRB')  # named "Receipt..." + sub-location
        cls.type_c = picking_type('Receipt Store C', 'incoming', cls.loc_c, 'GRC')
        cls.type_a_internal = picking_type('Shelving A', 'internal', cls.loc_a, 'GSA')  # not a receipt
        cls.stock_user.allowed_stock_location_ids = [(6, 0, (cls.loc_a | cls.loc_b).ids)]

    def test_custom_receipt_types_follow_allowed_locations(self):
        PickingType = self.env['stock.picking.type'].with_user(self.stock_user)
        types = PickingType._gw_custom_receipt_types()
        self.assertEqual(types, self.type_a | self.type_b)

        action = PickingType.gw_action_custom_receipts()
        self.assertEqual(action['res_model'], 'stock.picking.type')
        self.assertEqual(set(action['domain'][0][2]), set((self.type_a | self.type_b).ids))
        self.assertTrue(action['context']['gw_hide_custom_receipts_card'])

    def test_card_counts_and_pickings_action(self):
        receipt_a = self._create_picking(self.type_a, self.supplier_location, self.loc_a, [(self.product_a, 5)])
        self._create_picking(self.type_c, self.supplier_location, self.loc_c, [(self.product_a, 5)])
        self.assertEqual(receipt_a.state, 'assigned')

        data = self.env['stock.picking.type'].with_user(self.stock_user).gw_get_custom_receipts_data()
        self.assertTrue(data['show'])
        self.assertEqual(data['type_count'], 2)
        self.assertEqual(data['ready'], 1)

        action = self.env['stock.picking.type'].with_user(self.stock_user).gw_action_custom_receipts_pickings('assigned')
        pickings = self.env['stock.picking'].search(action['domain'])
        self.assertEqual(pickings, receipt_a)

    def test_card_hidden_without_allowed_locations(self):
        data = self.env['stock.picking.type'].with_user(self.receiver_user).gw_get_custom_receipts_data()
        self.assertFalse(data['show'])
        self.assertEqual(data['type_count'], 0)
