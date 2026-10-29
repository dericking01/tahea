from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .common import GwStockCommon


@tagged('post_install', '-at_install')
class TestPurchaseControls(GwStockCommon):

    def _confirmed_po(self, lines):
        po = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': qty,
                'price_unit': 10.0,
            }) for product, qty in lines],
        })
        po.button_confirm()
        return po

    def _receive(self, po, quantities=None):
        picking = po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for move in picking.move_ids:
            move.quantity = (quantities or {}).get(move.product_id, move.product_uom_qty)
        return picking, picking.button_validate()

    def _bill(self, po):
        action = po.action_create_invoice()
        return self.env['account.move'].browse(action['res_id'])

    # --- GRN (receipt) cannot exceed the PO quantity -----------------------------------

    def test_receipt_cannot_exceed_po_qty_all_lines_listed(self):
        po = self._confirmed_po([(self.product_a, 10), (self.product_b, 5), (self.product_c, 3)])
        with self.assertRaises(UserError) as err:
            self._receive(po, {self.product_a: 12, self.product_b: 6, self.product_c: 3})
        message = str(err.exception)
        self.assertIn('GW Product A', message)
        self.assertIn('GW Product B', message)
        self.assertNotIn('GW Product C', message)
        picking, _res = self._receive(po)
        self.assertEqual(picking.state, 'done')

    def test_receipt_backorder_cannot_exceed_remaining(self):
        po = self._confirmed_po([(self.product_a, 10)])
        picking, res = self._receive(po, {self.product_a: 6})
        Form.from_action(self.env, res).save().process()
        self.assertEqual(po.order_line.qty_received, 6)
        with self.assertRaises(UserError):
            self._receive(po, {self.product_a: 5})
        backorder, _res = self._receive(po, {self.product_a: 4})
        self.assertEqual(po.order_line.qty_received, 10)

    # --- Vendor bill from PO: quantity can't exceed original, UoM locked ----------------

    def test_bill_qty_cannot_exceed_original(self):
        po = self._confirmed_po([(self.product_a, 10), (self.product_b, 4)])
        self._receive(po)
        bill = self._bill(po)
        line_a = bill.invoice_line_ids.filtered(lambda l: l.product_id == self.product_a)
        self.assertEqual(line_a.po_original_qty, 10)
        self.assertTrue(line_a.po_qty_locked)

        with self.assertRaises(ValidationError):
            line_a.quantity = 12
        with self.assertRaises(ValidationError):
            with Form(bill) as bill_form:
                with bill_form.invoice_line_ids.edit(0) as line:
                    line.quantity = 11

        line_a.quantity = 7
        line_a.quantity = 10  # back up to the original value is allowed
        bill.invoice_date = '2026-10-29'
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    def test_bill_uom_cannot_change(self):
        po = self._confirmed_po([(self.product_a, 12)])
        self._receive(po)
        bill = self._bill(po)
        with self.assertRaises(ValidationError):
            bill.invoice_line_ids.product_uom_id = self.uom_dozen

    def test_bill_cannot_bill_more_than_received(self):
        po = self._confirmed_po([(self.product_a, 10)])
        _picking, res = self._receive(po, {self.product_a: 4})
        Form.from_action(self.env, res).save().process_cancel_backorder()
        bill = self._bill(po)
        self.assertEqual(bill.invoice_line_ids.quantity, 4)
        # A second bill for the same received goods (e.g. via auto-complete) is refused
        with self.assertRaises(ValidationError):
            self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'price_unit': 10.0,
                    'purchase_line_id': po.order_line.id,
                })],
            })

    def test_manual_bill_and_refund_unaffected(self):
        bill = self.init_invoice('in_invoice', products=self.product_a, post=False)
        bill.invoice_line_ids.quantity = 50
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    # --- Receipt lines: only administrators can delete them -----------------------------

    def test_receipt_line_delete_admin_only(self):
        po = self._confirmed_po([(self.product_a, 10), (self.product_b, 5)])
        receipt = po.picking_ids
        move_b = receipt.move_ids.filtered(lambda m: m.product_id == self.product_b)

        receipt_as_user = receipt.with_user(self.stock_user)
        self.assertFalse(receipt_as_user.gw_can_delete_moves)
        with self.assertRaises(UserError):
            receipt_as_user.write({'move_ids_without_package': [(2, move_b.id)]})
        with self.assertRaises(UserError):
            receipt_as_user.write({'move_ids': [(6, 0, (receipt.move_ids - move_b).ids)]})

        receipt_as_admin = receipt.with_user(self.admin_user)
        self.assertTrue(receipt_as_admin.gw_can_delete_moves)
        receipt_as_admin.write({'move_ids_without_package': [(2, move_b.id)]})
        self.assertEqual(len(receipt.move_ids), 1)

        # Other operation types keep the delete button
        internal = self._create_picking(self.warehouse.int_type_id, self.stock_location, self.stock_location, [(self.product_a, 1)])
        self.assertTrue(internal.with_user(self.stock_user).gw_can_delete_moves)

    def test_receipt_form_view_delete_option(self):
        arch = self.env['stock.picking'].with_user(self.stock_user).get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn("gw_can_delete_moves", arch)
