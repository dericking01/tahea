from odoo import Command
from odoo.addons.base.models.res_users import name_selection_groups
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import IntercompanyTransferCommon


@tagged('post_install', '-at_install', 'intercompany_stock_transfer')
class TestIntercompanyTransferSecurity(IntercompanyTransferCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_stock(cls.product_1, cls.loc_a1, 20)

    # 2
    def test_02_unauthorized_user_blocked_everywhere(self):
        Transfer = self._as(self.user_stock, self.env['intercompany.stock.transfer'])
        with self.assertRaises(AccessError):
            Transfer.create({
                'source_company_id': self.company_a.id, 'source_warehouse_id': self.wh_a1.id,
                'source_location_id': self.loc_a1.id, 'dest_company_id': self.company_b.id,
                'dest_warehouse_id': self.wh_b1.id, 'dest_location_id': self.loc_b1.id})

        transfer = self._create_transfer([(self.product_1, 5)])
        as_stock_user = self._as(self.user_stock, transfer)
        with self.assertRaises(AccessError):
            as_stock_user.read(['name'])
        for method in ('action_confirm', 'action_dispatch', 'action_receive', 'action_cancel',
                       'action_check_availability'):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(as_stock_user, method)()
        with self.assertRaises(AccessError):
            as_stock_user._action_cancel('nope')
        with self.assertRaises(AccessError):
            as_stock_user.write({'note': 'x'})

        # Plain Inventory rights do not allow processing the generated operations either.
        transfer.action_confirm()
        dispatch = self._as(self.user_stock, transfer._get_pickings('dispatch'))
        dispatch.read(['name'])  # ordinary inventory visibility is unchanged
        with self.assertRaises(AccessError):
            dispatch.button_validate()
        with self.assertRaises(AccessError):
            dispatch.action_cancel()
        self.assertEqual(transfer.state, 'confirmed')
        self.assertEqual(self._on_hand(self.product_1, self.loc_a1), 20)

    def test_02b_menu_and_action_hidden(self):
        menu = self.env.ref('intercompany_stock_transfer.menu_intercompany_transfer')
        visible_stock = self.env['ir.ui.menu'].with_user(self.user_stock)._visible_menu_ids()
        visible_ict = self.env['ir.ui.menu'].with_user(self.user_ict)._visible_menu_ids()
        self.assertNotIn(menu.id, visible_stock)
        self.assertIn(menu.id, visible_ict)
        self.assertFalse(self.user_stock.has_group('intercompany_stock_transfer.group_intercompany_transfer'),
                         "Inventory access does not grant the permission")

    # 3
    def test_03_permission_toggled_from_user_settings(self):
        field_name = name_selection_groups(self.group_ict.ids)
        field = self.env['res.users'].fields_get([field_name])[field_name]
        self.assertEqual(field['string'], 'Inter-Company Stock Transfers')
        self.assertIn((self.group_ict.id, 'Allow Inter-Company Stock Transfers'), field['selection'])
        # Rendered for administrators without debug mode (not hidden behind base.group_no_one).
        arch = self.env['res.users'].get_view(self.env.ref('base.view_users_form').id)['arch']
        self.assertIn(f'name="{field_name}"', arch)

        self.user_stock.write({field_name: self.group_ict.id})
        self.assertTrue(self.user_stock.has_group('intercompany_stock_transfer.group_intercompany_transfer'))
        transfer = self._create_transfer([(self.product_1, 1)], user=self.user_stock)
        self.assertTrue(transfer)

        self.user_stock.write({field_name: False})  # empty = revoked
        self.assertFalse(self.user_stock.has_group('intercompany_stock_transfer.group_intercompany_transfer'))
        self.assertTrue(self.user_stock.has_group('stock.group_stock_user'), "inventory rights are kept")
        with self.assertRaises(AccessError):
            self._as(self.user_stock, transfer).action_confirm()

    # 17
    def test_17_company_boundaries(self):
        # user_ict has companies A and B only.
        with self.assertRaises(AccessError):
            self._create_transfer([(self.product_1, 1)], dest_company_id=self.company_c.id,
                                  dest_warehouse_id=self.wh_c1.id, dest_location_id=self.wh_c1.lot_stock_id.id)
        with self.assertRaises(AccessError):
            self._as(self.user_ict, self.env['intercompany.stock.transfer'],
                     companies=self.company_a | self.company_c).search([])

        transfer_bc = self.env['intercompany.stock.transfer'].create({
            'source_company_id': self.company_b.id, 'source_warehouse_id': self.wh_b1.id,
            'source_location_id': self.loc_b1.id, 'dest_company_id': self.company_c.id,
            'dest_warehouse_id': self.wh_c1.id, 'dest_location_id': self.wh_c1.lot_stock_id.id,
            'line_ids': [Command.create({'product_id': self.product_1.id, 'product_uom_qty': 1})],
        })
        transfer_ac = transfer_bc.copy({
            'source_company_id': self.company_a.id, 'source_warehouse_id': self.wh_a1.id,
            'source_location_id': self.loc_a1.id})
        # Visible (one company is accessible) but not processable without access to both.
        self.assertIn(transfer_ac, self._as(self.user_ict, self.env['intercompany.stock.transfer']).search([]))
        with self.assertRaises(AccessError):
            self._as(self.user_ict, transfer_ac).action_confirm()
        # A user of company B only does not see A <-> C transfers at all.
        visible_b = self._as(self.user_ict_b, self.env['intercompany.stock.transfer'],
                             companies=self.company_b).search([])
        self.assertIn(transfer_bc, visible_b)
        self.assertNotIn(transfer_ac, visible_b)
        self.assertFalse(self._as(self.user_ict_b, self.env['intercompany.stock.transfer.line'],
                                  companies=self.company_b).search([('transfer_id', '=', transfer_ac.id)]))

    def test_17b_destination_only_user_can_receive_but_not_dispatch(self):
        transfer = self._create_transfer([(self.product_1, 4)])
        transfer.action_confirm()
        receiver = self._as(self.user_ict_b, transfer, companies=self.company_b)
        with self.assertRaises(AccessError):
            receiver.action_dispatch()
        transfer.action_dispatch()
        receiver.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(transfer.receive_user_id, self.user_ict_b)
        self.assertEqual(self._on_hand(self.product_1, self.loc_b1), 4)
        with self.assertRaises(AccessError):
            receiver._action_cancel('no access to source company')
