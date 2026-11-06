from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestPurchaseLock(GwStockCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.purchase_admin = new_test_user(
            cls.env, login='gw_purchase_admin', company_id=cls.company.id,
            company_ids=[(6, 0, cls.company.ids)],
            groups='base.group_system,purchase.group_purchase_manager,stock.group_stock_manager')

    def _po(self):
        return self.env['purchase.order'].with_user(self.purchase_admin).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': self.product_a.id, 'product_qty': 5, 'price_unit': 10})],
        })

    def test_draft_po_editable(self):
        po = self._po()
        po.order_line.product_qty = 7
        po.write({'partner_ref': 'REF1', 'order_line': [Command.create({'product_id': self.product_b.id, 'product_qty': 1})]})
        self.assertEqual(len(po.order_line), 2)

    def test_confirmed_po_readonly_even_for_admin(self):
        po = self._po()
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')
        line = po.order_line
        for action in (
            lambda: po.write({'partner_ref': 'X'}),
            lambda: line.write({'product_qty': 9}),
            lambda: line.write({'price_unit': 1}),
            lambda: po.write({'order_line': [Command.create({'product_id': self.product_b.id, 'product_qty': 1})]}),
            lambda: self.env['purchase.order.line'].with_user(self.purchase_admin).create(
                {'order_id': po.id, 'product_id': self.product_b.id, 'product_qty': 1}),
            lambda: line.unlink(),
        ):
            with self.assertRaises(UserError):
                action()
        self.assertEqual(line.product_qty, 5)
        # Normal flow still works: receive, bill, lock/unlock, chatter
        picking = po.picking_ids
        picking.move_ids.quantity = 5
        picking.with_user(self.purchase_admin).button_validate()
        self.assertEqual(line.qty_received, 5)
        po.action_create_invoice()
        self.assertEqual(line.qty_invoiced, 5)
        po.button_done()
        po.button_unlock()
        po.message_post(body='ok')

    def test_cancel_and_reset_to_draft_allows_amendment(self):
        po = self._po()
        po.button_confirm()
        po.button_cancel()
        po.button_draft()
        po.order_line.product_qty = 8
        self.assertEqual(po.order_line.product_qty, 8)

    def test_form_view_readonly_modifiers(self):
        arch = self.env['purchase.order'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn("state in ('to approve', 'purchase', 'done')", arch)
