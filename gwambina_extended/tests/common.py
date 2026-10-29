from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import new_test_user


class GwStockCommon(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.transit_location = cls.company.internal_transit_location_id
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')

        def product(name, **kw):
            return cls.env['product.product'].create(dict({
                'name': name,
                'is_storable': True,
                'purchase_method': 'receive',
                'standard_price': 10.0,
            }, **kw))

        cls.product_a = product('GW Product A')
        cls.product_b = product('GW Product B')
        cls.product_c = product('GW Product C')
        cls.product_d = product('GW Product D')

        user_vals = {'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)]}
        cls.stock_user = new_test_user(cls.env, login='gw_stock_user', groups='stock.group_stock_user', **user_vals)
        cls.receiver_user = new_test_user(cls.env, login='gw_receiver', groups='stock.group_stock_user', **user_vals)
        cls.other_user = new_test_user(cls.env, login='gw_other', groups='stock.group_stock_user', **user_vals)
        cls.admin_user = new_test_user(
            cls.env, login='gw_admin', groups='base.group_system,stock.group_stock_manager', **user_vals)

    @classmethod
    def _set_qty(cls, product, location, qty):
        cls.env['stock.quant']._update_available_quantity(product, location, qty)

    def _on_hand(self, product, location):
        quants = self.env['stock.quant'].search([('product_id', '=', product.id), ('location_id', '=', location.id)])
        return sum(quants.mapped('quantity'))

    @classmethod
    def _create_picking(cls, picking_type, location, location_dest, lines, user=None):
        env = cls.env(user=user) if user else cls.env
        picking = env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': location.id,
                'location_dest_id': location_dest.id,
            }) for product, qty in lines],
        })
        picking.action_confirm()
        return picking
