import unittest

from odoo import Command, fields
from odoo.tests import tagged

from .common import IntercompanyTransferCommon


@tagged('post_install', '-at_install', 'intercompany_stock_transfer')
class TestIntercompanyTransferValuation(IntercompanyTransferCommon):
    """Run only when stock_account is installed (valuation is optional)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'stock.valuation.layer' not in cls.env:
            raise unittest.SkipTest("stock_account is not installed")
        cls.categ_avco = cls.env['product.category'].create({'name': 'ICT AVCO'})
        for company in (cls.company_a, cls.company_b):
            cls.categ_avco.with_company(company).write({
                'property_cost_method': 'average',
                'property_valuation': 'manual_periodic',
            })
        cls.product_val = cls.env['product.product'].create({
            'name': 'ICT Valued Product', 'is_storable': True, 'categ_id': cls.categ_avco.id})
        cls.product_val.with_company(cls.company_a).standard_price = 10.0
        cls.product_val.with_company(cls.company_b).standard_price = 99.0

    def _layers(self, move):
        return self.env['stock.valuation.layer'].sudo().search([('stock_move_id', 'in', move.ids)])

    def _create_accounting(self, company, code):
        Account = self.env['account.account'].with_company(company)
        accounts = {
            key: Account.create({'name': f'{code} {key}', 'code': f'{code}{i}', 'account_type': atype,
                                 'company_ids': [Command.set(company.ids)]})
            for i, (key, atype) in enumerate([
                ('valuation', 'asset_current'), ('input', 'liability_current'),
                ('output', 'asset_current')], start=1)
        }
        journal = self.env['account.journal'].create({
            'name': f'{code} Stock Journal', 'code': f'S{code}', 'type': 'general', 'company_id': company.id})
        self.categ_avco.with_company(company).write({
            'property_valuation': 'real_time',
            'property_stock_valuation_account_id': accounts['valuation'].id,
            'property_stock_account_input_categ_id': accounts['input'].id,
            'property_stock_account_output_categ_id': accounts['output'].id,
            'property_stock_journal': journal.id,
        })
        return accounts

    # 18
    def test_18_valuation_layers_follow_each_company(self):
        self._add_stock(self.product_val, self.loc_a1, 10)
        transfer = self._create_transfer([(self.product_val, 4)])
        transfer.action_confirm()
        transfer.action_dispatch()
        dispatch_move = transfer._get_pickings('dispatch').move_ids
        out_layers = self._layers(dispatch_move)
        self.assertEqual(len(out_layers), 1)
        self.assertEqual(out_layers.company_id, self.company_a)
        self.assertAlmostEqual(out_layers.value, -40.0)
        self.assertAlmostEqual(out_layers.quantity, -4)
        receipt_move = transfer._get_pickings('receipt').move_ids
        self.assertFalse(self._layers(receipt_move), "nothing is valued in B before the receipt")
        self.assertAlmostEqual(receipt_move.price_unit, 10.0, msg="source cost carried to the receipt")

        transfer.action_receive()
        in_layers = self._layers(receipt_move)
        self.assertEqual(len(in_layers), 1)
        self.assertEqual(in_layers.company_id, self.company_b)
        self.assertAlmostEqual(in_layers.value, 40.0)
        self.assertAlmostEqual(self.product_val.with_company(self.company_a).value_svl, 60.0)
        self.assertAlmostEqual(self.product_val.with_company(self.company_b).value_svl, 40.0)
        # AVCO in B is updated from the transferred cost (was 99 with no stock).
        self.assertAlmostEqual(self.product_val.with_company(self.company_b).standard_price, 10.0)
        self.assertFalse(dispatch_move.account_move_ids | receipt_move.account_move_ids,
                         "periodic valuation: no journal entries")

    def test_18b_real_time_entries_balanced_per_company(self):
        acc_a = self._create_accounting(self.company_a, 'A')
        acc_b = self._create_accounting(self.company_b, 'B')
        self._add_stock(self.product_val, self.loc_a1, 10)
        transfer = self._create_transfer([(self.product_val, 3)])
        transfer.action_confirm()
        transfer.action_dispatch()
        transfer.action_receive()
        dispatch_move = transfer._get_pickings('dispatch').move_ids
        receipt_move = transfer._get_pickings('receipt').move_ids

        out_am = dispatch_move.account_move_ids
        self.assertEqual(len(out_am), 1)
        self.assertEqual(out_am.company_id, self.company_a)
        self.assertEqual(out_am.state, 'posted')
        self.assertAlmostEqual(out_am.line_ids.filtered(lambda l: l.account_id == acc_a['valuation']).balance, -30)
        self.assertAlmostEqual(out_am.line_ids.filtered(lambda l: l.account_id == acc_a['output']).balance, 30)

        in_am = receipt_move.account_move_ids
        self.assertEqual(len(in_am), 1)
        self.assertEqual(in_am.company_id, self.company_b)
        self.assertAlmostEqual(in_am.line_ids.filtered(lambda l: l.account_id == acc_b['valuation']).balance, 30)
        self.assertAlmostEqual(in_am.line_ids.filtered(lambda l: l.account_id == acc_b['input']).balance, -30)

    def test_18c_cancel_return_revalues_at_original_cost(self):
        self._add_stock(self.product_val, self.loc_a1, 10)
        transfer = self._create_transfer([(self.product_val, 5)])
        transfer.action_confirm()
        transfer.action_dispatch()
        returns = transfer._action_cancel('cancelled in transit')
        self._validate(returns)
        self.assertAlmostEqual(self._layers(returns.move_ids).value, 50.0)
        self.assertAlmostEqual(self.product_val.with_company(self.company_a).value_svl, 100.0)
        self.assertAlmostEqual(self.product_val.with_company(self.company_b).value_svl, 0.0)

    def test_18d_currency_conversion(self):
        source_currency = self.company_a.currency_id
        other = self.env.ref('base.EUR') if source_currency != self.env.ref('base.EUR') else self.env.ref('base.USD')
        other.active = True
        self.env['res.currency.rate'].create({
            'currency_id': other.id, 'rate': 2.0, 'name': '2000-01-01', 'company_id': False})
        self.env['res.currency.rate'].search([
            ('currency_id', '=', source_currency.id), ('company_id', '=', False)]).unlink()
        company_d = self.env['res.company'].create({'name': 'Delta ICT Co', 'currency_id': other.id})
        self.user_ict.company_ids = [Command.link(company_d.id)]
        self.categ_avco.with_company(company_d).write({
            'property_cost_method': 'average', 'property_valuation': 'manual_periodic'})
        wh_d = self.env['stock.warehouse'].search([('company_id', '=', company_d.id)], limit=1)
        self._add_stock(self.product_val, self.loc_a1, 2)
        transfer = self._create_transfer(
            [(self.product_val, 2)], dest_company_id=company_d.id,
            dest_warehouse_id=wh_d.id, dest_location_id=wh_d.lot_stock_id.id)
        transfer = transfer.with_context(allowed_company_ids=(self.company_a | company_d).ids)
        transfer.action_confirm()
        transfer.action_dispatch()
        expected = source_currency._convert(10.0, other, company_d, fields.Date.today())
        self.assertNotAlmostEqual(expected, 10.0)
        receipt_move = transfer._get_pickings('receipt').move_ids
        self.assertAlmostEqual(receipt_move.price_unit, expected)
        transfer.action_receive()
        self.assertAlmostEqual(self._layers(receipt_move).value, expected * 2)

    def test_18e_each_receipt_priced_from_its_own_shipment(self):
        self._add_stock(self.product_val, self.loc_a1, 10)
        transfer = self._create_transfer([(self.product_val, 10)])
        transfer.action_confirm()
        dispatch = transfer._get_pickings('dispatch')
        self._set_quantity(dispatch.move_ids, 4)
        self._validate(self._as(self.user_ict, dispatch), backorder=True)
        first_receipt = transfer._get_pickings('receipt')
        self.assertAlmostEqual(first_receipt.move_ids.price_unit, 10.0)
        # AVCO revaluation in A between the two shipments.
        self.product_val.with_company(self.company_a).standard_price = 30.0
        transfer.action_dispatch()
        second_receipt = transfer._get_pickings('receipt') - first_receipt
        self.assertAlmostEqual(second_receipt.move_ids.price_unit, 30.0)
        self.assertEqual(second_receipt.move_ids.move_orig_ids,
                         transfer._get_pickings('dispatch').filtered('backorder_id').move_ids)
        transfer.action_receive()
        for receipt in transfer._get_pickings('receipt', open_only=True):
            self._validate(self._as(self.user_ict, receipt))
        self.assertEqual(transfer.state, 'received')
        self.assertAlmostEqual(self.product_val.with_company(self.company_b).value_svl, 4 * 10.0 + 6 * 30.0)
