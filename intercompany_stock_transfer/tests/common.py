from odoo import Command
from odoo.tests import Form, TransactionCase


class IntercompanyTransferCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        Company = cls.env['res.company']
        # Creating companies in test mode also creates one warehouse each and
        # activates the native inter-company transit location.
        cls.company_a = Company.create({'name': 'Alpha ICT Co'})
        cls.company_b = Company.create({'name': 'Beta ICT Co'})
        cls.company_c = Company.create({'name': 'Gamma ICT Co'})
        cls.branch_a = Company.create({'name': 'Alpha ICT Branch', 'parent_id': cls.company_a.id})
        Warehouse = cls.env['stock.warehouse']
        cls.wh_a1 = Warehouse.search([('company_id', '=', cls.company_a.id)], limit=1)
        cls.wh_a2 = Warehouse.create({'name': 'ICT A2', 'code': 'ICTA2', 'company_id': cls.company_a.id})
        cls.wh_b1 = Warehouse.search([('company_id', '=', cls.company_b.id)], limit=1)
        cls.wh_b2 = Warehouse.create({'name': 'ICT B2', 'code': 'ICTB2', 'company_id': cls.company_b.id})
        cls.wh_c1 = Warehouse.search([('company_id', '=', cls.company_c.id)], limit=1)
        cls.wh_branch_a = Warehouse.search([('company_id', '=', cls.branch_a.id)], limit=1)
        cls.loc_a1 = cls.wh_a1.lot_stock_id
        cls.loc_b1 = cls.wh_b1.lot_stock_id
        cls.shelf_a1 = cls.env['stock.location'].create({
            'name': 'Shelf A1', 'location_id': cls.loc_a1.id, 'usage': 'internal',
            'company_id': cls.company_a.id})
        cls.shelf_b1 = cls.env['stock.location'].create({
            'name': 'Shelf B1', 'location_id': cls.loc_b1.id, 'usage': 'internal',
            'company_id': cls.company_b.id})
        cls.transit = cls.env.ref('stock.stock_location_inter_company')

        cls.group_ict = cls.env.ref('intercompany_stock_transfer.group_intercompany_transfer')
        base_groups = [
            cls.env.ref('base.group_user').id,
            cls.env.ref('stock.group_stock_user').id,
            cls.env.ref('stock.group_production_lot').id,
            cls.env.ref('base.group_multi_company').id,
        ]
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_ict = Users.create({
            'name': 'ICT User', 'login': 'ict_user', 'email': 'ict_user@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [Command.set((cls.company_a | cls.company_b | cls.branch_a).ids)],
            'groups_id': [Command.set(base_groups + [cls.group_ict.id])],
        })
        cls.user_stock = Users.create({
            'name': 'Stock User', 'login': 'ict_stock_user', 'email': 'ict_stock_user@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [Command.set((cls.company_a | cls.company_b).ids)],
            'groups_id': [Command.set(base_groups)],
        })
        cls.user_ict_b = Users.create({
            'name': 'ICT Receiver B', 'login': 'ict_user_b', 'email': 'ict_user_b@example.com',
            'company_id': cls.company_b.id,
            'company_ids': [Command.set(cls.company_b.ids)],
            'groups_id': [Command.set(base_groups + [cls.group_ict.id])],
        })

        Product = cls.env['product.product']
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')
        cls.product_1 = Product.create({'name': 'ICT Product 1', 'is_storable': True, 'standard_price': 10.0})
        cls.product_2 = Product.create({'name': 'ICT Product 2', 'is_storable': True, 'standard_price': 5.0})
        cls.product_lot = Product.create({'name': 'ICT Lot Product', 'is_storable': True, 'tracking': 'lot'})
        cls.product_serial = Product.create({'name': 'ICT Serial Product', 'is_storable': True, 'tracking': 'serial'})
        cls.product_consu = Product.create({'name': 'ICT Consumable', 'type': 'consu', 'is_storable': False})
        cls.product_a_only = Product.create({
            'name': 'ICT A-only Product', 'is_storable': True, 'company_id': cls.company_a.id})
        cls.lot_1 = cls.env['stock.lot'].create({'name': 'LOT-001', 'product_id': cls.product_lot.id})
        cls.lot_2 = cls.env['stock.lot'].create({'name': 'LOT-002', 'product_id': cls.product_lot.id})
        cls.serials = cls.env['stock.lot'].create([
            {'name': f'SN-{i}', 'product_id': cls.product_serial.id} for i in range(1, 4)])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _add_stock(cls, product, location, qty, lot=None):
        """Native inventory adjustment (creates moves and valuation layers)."""
        quant = cls.env['stock.quant'].with_company(location.company_id).with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': location.id,
            'inventory_quantity': qty,
            'lot_id': lot.id if lot else False,
        })
        quant.action_apply_inventory()

    def _on_hand(self, product, location, lot=None):
        quants = self.env['stock.quant'].sudo()._gather(product, location, lot_id=lot)
        return sum(quants.mapped('quantity'))

    def _as(self, user, records, companies=None):
        companies = companies or (self.company_a | self.company_b)
        return records.with_user(user).with_context(allowed_company_ids=companies.ids)

    def _create_transfer(self, lines, user=None, **values):
        user = user or self.user_ict
        vals = {
            'source_company_id': self.company_a.id,
            'source_warehouse_id': self.wh_a1.id,
            'source_location_id': self.loc_a1.id,
            'dest_company_id': self.company_b.id,
            'dest_warehouse_id': self.wh_b1.id,
            'dest_location_id': self.loc_b1.id,
            'line_ids': [Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
                **(extra[0] if extra else {}),
            }) for product, qty, *extra in lines],
        }
        vals.update(values)
        return self._as(user, self.env['intercompany.stock.transfer']).create(vals)

    def _validate(self, pickings, backorder=True):
        """Validate pickings like a user would, answering the backorder wizard."""
        res = pickings.button_validate()
        if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
            wizard = Form(self.env['stock.backorder.confirmation'].with_user(pickings.env.user).with_context(
                res['context'])).save()
            if backorder:
                wizard.process()
            else:
                wizard.process_cancel_backorder()
        return res

    def _set_quantity(self, move, qty):
        move.quantity = qty
        move.picked = True
