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

    def _grns(self, user):
        action = self.env['stock.picking.type'].with_user(user).gw_action_custom_receipts()
        self.assertEqual(action['res_model'], 'stock.picking')
        self.assertNotIn('help', action)
        return self.env['stock.picking'].search(action['domain'])

    def test_card_opens_grns_to_allowed_locations(self):
        grn_a = self._create_picking(self.type_a, self.supplier_location, self.loc_a, [(self.product_a, 5)])
        grn_b = self._create_picking(self.type_b, self.stock_location, self.loc_b_bin, [(self.product_a, 1)])
        grn_c = self._create_picking(self.type_c, self.supplier_location, self.loc_c, [(self.product_a, 5)])
        shelving = self._create_picking(self.type_a_internal, self.stock_location, self.loc_a, [(self.product_a, 1)])
        # Standard warehouse receipt type ending in an allowed location also counts
        grn_wh = self._create_picking(self.warehouse.in_type_id, self.supplier_location, self.loc_a, [(self.product_b, 2)])

        grns = self._grns(self.stock_user)
        self.assertIn(grn_a, grns)
        self.assertIn(grn_b, grns)
        self.assertIn(grn_wh, grns)
        self.assertNotIn(grn_c, grns)
        self.assertNotIn(shelving, grns)

        data = self.env['stock.picking.type'].with_user(self.stock_user).gw_get_custom_receipts_data()
        self.assertTrue(data['show'])
        self.assertEqual(data['ready'], len(grns.filtered(lambda p: p.state == 'assigned')))

    def test_receipt_confirmations_excluded(self):
        self.loc_a.gw_responsible_user_ids = [(6, 0, self.receiver_user.ids)]
        self._set_qty(self.product_a, self.loc_c, 3)
        transfer = self._create_picking(self.warehouse.int_type_id, self.loc_c, self.loc_a, [(self.product_a, 3)])
        transfer.action_assign()
        transfer.button_validate()
        confirmation = transfer.gw_receipt_picking_ids
        self.assertTrue(confirmation)
        self.assertNotIn(confirmation, self._grns(self.stock_user))

    def test_card_hidden_without_allowed_locations(self):
        data = self.env['stock.picking.type'].with_user(self.receiver_user).gw_get_custom_receipts_data()
        self.assertFalse(data['show'])
        self.assertFalse(self._grns(self.receiver_user))

    def test_card_hidden_when_allowed_locations_archived(self):
        self.loc_a.active = False
        self.loc_b_bin.active = False
        self.loc_b.active = False
        data = self.env['stock.picking.type'].with_user(self.stock_user).gw_get_custom_receipts_data()
        self.assertFalse(data['show'])
