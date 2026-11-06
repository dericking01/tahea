from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged

from .common import IntercompanyTransferCommon


@tagged('post_install', '-at_install', 'intercompany_stock_transfer')
class TestDelegatedBranchTransfers(IntercompanyTransferCommon):
    """A branch user sends stock to a sibling branch it is NOT allowed in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.primesoft = Company.create({'name': 'Primesoft ICT'})
        cls.branch_1 = Company.create({'name': 'Prime Branch 1', 'parent_id': cls.primesoft.id})
        cls.branch_2 = Company.create({'name': 'Prime Branch 2', 'parent_id': cls.primesoft.id})
        Warehouse = cls.env['stock.warehouse']
        cls.wh_p = Warehouse.search([('company_id', '=', cls.primesoft.id)], limit=1)
        cls.wh_1 = Warehouse.search([('company_id', '=', cls.branch_1.id)], limit=1)
        cls.wh_2 = Warehouse.search([('company_id', '=', cls.branch_2.id)], limit=1)
        cls.shelf_2 = cls.env['stock.location'].create({
            'name': 'Shelf P2', 'location_id': cls.wh_2.lot_stock_id.id, 'company_id': cls.branch_2.id})
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('stock.group_stock_user').id,
                  cls.group_ict.id]
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_br1 = Users.create({
            'name': 'Branch 1 User', 'login': 'ict_br1', 'email': 'br1@example.com',
            'company_id': cls.branch_1.id, 'company_ids': [Command.set(cls.branch_1.ids)],
            'groups_id': [Command.set(groups)]})
        cls.user_br2 = Users.create({
            'name': 'Branch 2 User', 'login': 'ict_br2', 'email': 'br2@example.com',
            'company_id': cls.branch_2.id, 'company_ids': [Command.set(cls.branch_2.ids)],
            'groups_id': [Command.set(groups)]})
        cls._add_stock(cls.product_1, cls.wh_1.lot_stock_id, 10)
        cls._add_stock(cls.product_1, cls.wh_2.lot_stock_id, 7)

    def _br1(self, records):
        # Tracking enabled on purpose: chatter tracking must not read branch 2.
        return records.with_user(self.user_br1).with_context(
            allowed_company_ids=self.branch_1.ids, tracking_disable=False)

    def _br2(self, records):
        return records.with_user(self.user_br2).with_context(allowed_company_ids=self.branch_2.ids)

    def _vals(self, **extra):
        vals = {
            'source_company_id': self.branch_1.id, 'source_warehouse_id': self.wh_1.id,
            'source_location_id': self.wh_1.lot_stock_id.id,
            'dest_company_id': self.branch_2.id, 'dest_warehouse_id': self.wh_2.id,
            'dest_location_id': self.shelf_2.id,
            'line_ids': [Command.create({'product_id': self.product_1.id, 'product_uom_qty': 4})],
        }
        vals.update(extra)
        return vals

    def test_sibling_branch_stays_inaccessible(self):
        # Not selectable in the company switcher...
        with self.assertRaises(AccessError):
            self.env['stock.warehouse'].with_user(self.user_br1).with_context(
                allowed_company_ids=(self.branch_1 | self.branch_2).ids).search([])
        # ...and its stock/warehouses are invisible through normal screens.
        Quant = self._br1(self.env['stock.quant'])
        self.assertFalse(Quant.search([('company_id', '=', self.branch_2.id)]))
        self.assertFalse(self._br1(self.env['stock.warehouse']).search([('company_id', '=', self.branch_2.id)]))
        with self.assertRaises(AccessError):
            self._br1(self.wh_2).read(['name'])
        with self.assertRaises(AccessError):
            self._br1(self.wh_2.lot_stock_id).read(['name'])

    def test_form_offers_sibling_branches_only(self):
        Transfer = self._br1(self.env['intercompany.stock.transfer'])
        values = Transfer.onchange({}, [], {
            'state': {}, 'source_company_id': {}, 'dest_company_id': {},
            'allowed_company_ids': {}, 'allowed_parent_company_ids': {},
            'allowed_dest_company_ids': {}, 'allowed_dest_parent_company_ids': {}})['value']
        self.assertEqual(values['allowed_company_ids'], self.branch_1.ids, "source: own branch only")
        self.assertEqual(set(values['allowed_dest_parent_company_ids']), set((self.branch_1 | self.branch_2).ids))
        self.assertNotIn(self.primesoft.id, values['allowed_dest_company_ids'], "not the parent company")
        self.assertNotIn(self.branch_a.id, values['allowed_dest_company_ids'], "not other companies' branches")

        ctx = {'ict_delegated_targets': True}
        Company = self._br1(self.env['res.company']).with_context(ctx)
        self.assertIn(self.branch_2.id, [r[0] for r in Company.name_search(
            'Prime', [('id', 'in', values['allowed_dest_parent_company_ids'])])])
        warehouses = self._br1(self.env['stock.warehouse']).with_context(ctx).name_search(
            '', [('company_id', 'child_of', self.branch_2.id)])
        self.assertEqual([r[0] for r in warehouses], self.wh_2.ids)
        locations = [r[0] for r in self._br1(self.env['stock.location']).with_context(ctx).name_search(
            '', [('usage', '=', 'internal'), ('warehouse_id', '=', self.wh_2.id)])]
        self.assertIn(self.shelf_2.id, locations)
        self.assertNotIn(self.wh_p.lot_stock_id.id, locations)
        # Without the form's switch, nothing of branch 2 is suggested.
        self.assertFalse(self._br1(self.env['stock.warehouse']).name_search(
            '', [('company_id', 'child_of', self.branch_2.id)]))
        # The switch never exposes the parent company's or another company's warehouses.
        self.assertFalse(self._br1(self.env['stock.warehouse']).with_context(ctx).name_search(
            '', [('company_id', 'in', (self.primesoft | self.company_a | self.branch_a).ids)]))

    def test_form_flow_and_full_transfer(self):
        form = Form(self._br1(self.env['intercompany.stock.transfer']))
        self.assertEqual(form.source_company_id, self.branch_1)
        self.assertEqual(form.source_warehouse_id, self.wh_1)
        form.dest_parent_company_id = self.branch_2
        self.assertEqual(form.dest_warehouse_id, self.wh_2, "single warehouse proposed")
        form.dest_location_id = self.shelf_2
        with form.line_ids.new() as line:
            line.product_id = self.product_1
            line.product_uom_qty = 4
        transfer = form.save()
        self.assertEqual(transfer.dest_company_id, self.branch_2)
        self.assertFalse(transfer.can_access_dest)

        transfer.action_confirm()
        transfer.action_dispatch()
        self.assertEqual(transfer.state, 'in_transit')
        receipt = transfer.sudo()._get_pickings('receipt')
        self.assertEqual(receipt.company_id, self.branch_2)
        self.assertEqual(receipt.location_dest_id, self.shelf_2)
        self.assertEqual(receipt.create_uid, self.user_br1, "audit keeps the real author")
        self.assertNotIn(self.user_br1.partner_id, receipt.message_partner_ids,
                         "sender is not subscribed to the other branch's receipt")
        self.assertFalse(transfer.can_receive, "the sender cannot receive into branch 2")
        with self.assertRaises(AccessError):
            transfer.action_receive()
        with self.assertRaises(AccessError):
            self._br1(receipt).read(['name'])
        self.assertEqual(self._on_hand(self.product_1, self.wh_1.lot_stock_id), 6)
        self.assertEqual(self._on_hand(self.product_1, self.wh_2.lot_stock_id), 7, "nothing received yet")

        # Branch 2's own user sees the transfer and receives it.
        incoming = self._br2(transfer)
        self.assertTrue(incoming.can_receive)
        incoming.action_receive()
        self.assertEqual(transfer.state, 'received')
        self.assertEqual(self._on_hand(self.product_1, self.shelf_2), 4)
        self.assertEqual(transfer.line_ids.qty_received, 4)

    def test_cancel_after_dispatch_by_sender(self):
        transfer = self._br1(self.env['intercompany.stock.transfer']).create(self._vals())
        transfer.action_confirm()
        transfer.action_dispatch()
        returns = transfer._action_cancel('Wrong branch')
        receipt = transfer.sudo()._get_pickings('receipt')
        self.assertEqual(receipt.state, 'cancel')
        self.assertEqual(returns.company_id, self.branch_1)
        self._validate(self._br1(returns))
        self.assertEqual(self._on_hand(self.product_1, self.wh_1.lot_stock_id), 10)

    def test_only_sibling_branches_can_be_targeted(self):
        Transfer = self._br1(self.env['intercompany.stock.transfer'])
        # The parent company itself is not a delegated destination.
        with self.assertRaises(AccessError):
            Transfer.create(self._vals(dest_company_id=self.primesoft.id, dest_warehouse_id=self.wh_p.id,
                                       dest_location_id=self.wh_p.lot_stock_id.id))
        # Nor are other companies or their branches.
        with self.assertRaises(AccessError):
            Transfer.create(self._vals(dest_company_id=self.branch_a.id, dest_warehouse_id=self.wh_branch_a.id,
                                       dest_location_id=self.wh_branch_a.lot_stock_id.id))
        # The sibling cannot be used as SOURCE (stock of a branch the user is not in).
        with self.assertRaises(AccessError):
            Transfer.create(self._vals(
                source_company_id=self.branch_2.id, source_warehouse_id=self.wh_2.id,
                source_location_id=self.wh_2.lot_stock_id.id,
                dest_company_id=self.branch_1.id, dest_warehouse_id=self.wh_1.id,
                dest_location_id=self.wh_1.lot_stock_id.id))

    def test_users_only_see_their_own_branch_transfers(self):
        transfer = self._br1(self.env['intercompany.stock.transfer']).create(self._vals())
        self.assertIn(transfer, self._br2(self.env['intercompany.stock.transfer']).search([]),
                      "the receiving branch sees incoming transfers")
        other_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other', 'login': 'ict_other', 'company_id': self.company_a.id,
            'company_ids': [Command.set(self.company_a.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id, self.group_ict.id])]})
        self.assertNotIn(transfer, self.env['intercompany.stock.transfer'].with_user(other_user).search([]))

    def test_list_and_grouping_for_sender(self):
        Transfer = self._br1(self.env['intercompany.stock.transfer'])
        transfer = Transfer.create(self._vals())
        rows = Transfer.web_search_read([], {
            'name': {}, 'dest_parent_company_id': {'fields': {'display_name': {}}},
            'dest_warehouse_id': {'fields': {'display_name': {}}},
            'dest_location_id': {'fields': {'display_name': {}}}})['records']
        row = next(r for r in rows if r['id'] == transfer.id)
        self.assertEqual(row['dest_warehouse_id']['display_name'], self.wh_2.display_name)
        groups = Transfer.web_read_group([], ['dest_parent_company_id'], ['dest_parent_company_id'])['groups']
        self.assertIn((self.branch_2.id, self.branch_2.display_name),
                      [tuple(g['dest_parent_company_id']) for g in groups])
