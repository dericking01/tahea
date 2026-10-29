from odoo.tests import tagged

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestLocationRestriction(GwStockCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loc_1 = cls.env['stock.location'].create({'name': 'GW Allowed', 'location_id': cls.stock_location.id})
        cls.loc_2 = cls.env['stock.location'].create({'name': 'GW Forbidden', 'location_id': cls.stock_location.id})
        cls.loc_1_child = cls.env['stock.location'].create({'name': 'GW Allowed Bin', 'location_id': cls.loc_1.id})
        cls._set_qty(cls.product_a, cls.loc_1_child, 5)
        cls._set_qty(cls.product_a, cls.loc_2, 7)
        cls.stock_user.write({
            'restrict_stock_locations': True,
            'allowed_stock_location_ids': [(6, 0, cls.loc_1.ids)],
        })
        cls.receipt_forbidden = cls._create_picking(
            cls.warehouse.in_type_id, cls.supplier_location, cls.loc_2, [(cls.product_a, 1)])
        cls.receipt_allowed = cls._create_picking(
            cls.warehouse.in_type_id, cls.supplier_location, cls.loc_1, [(cls.product_a, 1)])
        cls.delivery_forbidden = cls._create_picking(
            cls.warehouse.out_type_id, cls.loc_2, cls.customer_location, [(cls.product_a, 1)])
        cls.internal_forbidden = cls._create_picking(
            cls.warehouse.int_type_id, cls.loc_2, cls.stock_location, [(cls.product_a, 1)])

    def _ids(self, model, user, domain):
        records = self.env[model].with_user(user).web_search_read(domain, {'id': {}})['records']
        return {r['id'] for r in records}

    def test_quants_restricted(self):
        domain = [('product_id', '=', self.product_a.id)]
        quant_child = self.env['stock.quant'].search([('location_id', '=', self.loc_1_child.id)])
        quant_2 = self.env['stock.quant'].search([('location_id', '=', self.loc_2.id)])
        visible = self._ids('stock.quant', self.stock_user, domain)
        self.assertIn(quant_child.id, visible)
        self.assertNotIn(quant_2.id, visible)
        self.assertIn(quant_2.id, self._ids('stock.quant', self.receiver_user, domain))
        groups = self.env['stock.quant'].with_user(self.stock_user).web_read_group(
            domain, ['quantity:sum'], ['product_id'])
        self.assertEqual(groups['groups'][0]['quantity'], 5)

    def test_pickings_restricted_but_internal_and_deliveries_visible(self):
        domain = [('product_id', '=', self.product_a.id)]
        visible = self._ids('stock.picking', self.stock_user, domain)
        self.assertIn(self.receipt_allowed.id, visible)
        self.assertNotIn(self.receipt_forbidden.id, visible)
        self.assertIn(self.delivery_forbidden.id, visible)
        self.assertIn(self.internal_forbidden.id, visible)
        self.assertIn(self.receipt_forbidden.id, self._ids('stock.picking', self.receiver_user, domain))

    def test_locations_and_warehouses(self):
        visible = self._ids('stock.location', self.stock_user, [])
        self.assertIn(self.loc_1.id, visible)
        self.assertIn(self.loc_1_child.id, visible)
        self.assertNotIn(self.loc_2.id, visible)
        self.assertIn(self.customer_location.id, visible)
        self.assertIn(self.warehouse.id, self._ids('stock.warehouse', self.stock_user, []))

        names = self.env['stock.location'].with_user(self.stock_user).with_context(
            gw_restrict_locations=True).name_search('GW ')
        self.assertNotIn(self.loc_2.id, [n[0] for n in names])
        # Without the context key (e.g. destination of an internal transfer) everything is proposed
        names = self.env['stock.location'].with_user(self.stock_user).name_search('GW ')
        self.assertIn(self.loc_2.id, [n[0] for n in names])

    def test_business_logic_not_affected(self):
        # A restricted user can still validate an internal transfer from a forbidden location
        picking = self.internal_forbidden.with_user(self.stock_user)
        picking.action_assign()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._on_hand(self.product_a, self.loc_2), 6)
