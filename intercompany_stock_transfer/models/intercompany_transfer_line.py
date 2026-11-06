from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class IntercompanyStockTransferLine(models.Model):
    _name = 'intercompany.stock.transfer.line'
    _description = 'Inter-Company Stock Transfer Line'
    _order = 'transfer_id, sequence, id'
    _check_company_auto = True

    transfer_id = fields.Many2one(
        'intercompany.stock.transfer', 'Transfer', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(related='transfer_id.state')
    company_id = fields.Many2one(
        'res.company', related='transfer_id.source_company_id', store=True, index=True)
    product_id = fields.Many2one(
        'product.product', 'Product', required=True,
        domain="[('is_storable', '=', True), '|', ('company_id', '=', False), "
               "'&', ('company_id', 'parent_of', parent.source_company_id), "
               "('company_id', 'parent_of', parent.dest_company_id)]")
    product_tracking = fields.Selection(related='product_id.tracking')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_uom_id = fields.Many2one(
        'uom.uom', 'Unit of Measure', required=True,
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_qty = fields.Float(
        'Quantity Requested', digits='Product Unit of Measure', required=True, default=1.0)
    lot_id = fields.Many2one(
        'stock.lot', 'Lot/Serial Number', check_company=True,
        domain="[('product_id', '=', product_id)]",
        help="Optional: reserve this specific lot/serial number at the source. Leave empty "
             "to let the source operation pick lots (they can be chosen on the operation).")

    source_qty_available = fields.Float(
        'Source Availability', digits='Product Unit of Measure',
        compute='_compute_source_qty_available',
        help="Quantity not reserved by other operations at the source location "
             "(including its sub-locations), in this line's unit of measure.")
    qty_reserved = fields.Float('Reserved', digits='Product Unit of Measure', compute='_compute_quantities')
    qty_dispatched = fields.Float('Dispatched', digits='Product Unit of Measure', compute='_compute_quantities')
    qty_in_transit = fields.Float('In Transit', digits='Product Unit of Measure', compute='_compute_quantities')
    qty_received = fields.Float('Received', digits='Product Unit of Measure', compute='_compute_quantities')
    lot_names = fields.Char('Dispatched Lots/Serials', compute='_compute_quantities')
    move_ids = fields.One2many('stock.move', 'intercompany_line_id', 'Stock Moves', readonly=True)

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            if not line.product_uom_id or line.product_uom_id.category_id != line.product_id.uom_id.category_id:
                line.product_uom_id = line.product_id.uom_id

    @api.depends('product_id', 'product_uom_id', 'transfer_id.source_location_id',
                 'transfer_id.source_company_id')
    def _compute_source_qty_available(self):
        for line in self:
            location = line.transfer_id.source_location_id
            if not line.product_id or not location or not line.product_uom_id:
                line.source_qty_available = 0.0
                continue
            # Informational read-only figure; sudo so that it is displayed even
            # when the source company is not active in the company switcher.
            product = line.product_id.sudo().with_company(line.transfer_id.source_company_id).with_context(
                location=location.id)
            line.source_qty_available = product.uom_id._compute_quantity(
                product.free_qty, line.product_uom_id)

    @api.depends('move_ids.state', 'move_ids.quantity', 'move_ids.product_uom_qty',
                 'move_ids.move_line_ids.quantity', 'move_ids.move_line_ids.lot_id')
    def _compute_quantities(self):
        lines = self.filtered(lambda l: l.id and l.transfer_id.id)
        balances = lines.transfer_id._get_balances() if lines else {}
        for line in self:
            bal = balances.get(line.id)
            if not bal:
                line.update({'qty_reserved': 0.0, 'qty_dispatched': 0.0, 'qty_in_transit': 0.0,
                             'qty_received': 0.0, 'lot_names': False})
                continue
            to_line_uom = lambda qty: line.product_id.uom_id._compute_quantity(qty, line.product_uom_id)  # noqa: E731
            line.qty_reserved = to_line_uom(bal['reserved'])
            line.qty_dispatched = to_line_uom(bal['dispatched_net'])
            line.qty_received = to_line_uom(bal['received_net'])
            line.qty_in_transit = to_line_uom(bal['in_transit'])
            line.lot_names = ', '.join(sorted(k for k in bal['transit_lots'] if k)) or False

    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for line in self:
            if float_compare(line.product_uom_qty, 0, precision_rounding=line.product_uom_id.rounding or 0.01) <= 0:
                raise ValidationError(_(
                    "The requested quantity of %s must be strictly positive.", line.product_id.display_name))

    @api.constrains('product_id', 'product_uom_id', 'lot_id')
    def _check_line_validity(self):
        # sudo: validation only, so it also works when one of the two
        # companies is not active in the company switcher.
        for line in self.sudo():
            product = line.product_id
            transfer = line.transfer_id
            if not product.is_storable:
                raise ValidationError(_(
                    "%s is not tracked in inventory; only storable products can be transferred.",
                    product.display_name))
            if not product.active:
                raise ValidationError(_("%s is archived.", product.display_name))
            if product.company_id:
                allowed = product.company_id | product.company_id.all_child_ids
                if transfer.source_company_id not in allowed or transfer.dest_company_id not in allowed:
                    raise ValidationError(_(
                        "%(product)s belongs to %(company)s and cannot be shared between "
                        "%(src)s and %(dst)s.", product=product.display_name,
                        company=product.company_id.name, src=transfer.source_company_id.name,
                        dst=transfer.dest_company_id.name))
            if line.product_uom_id.category_id != product.uom_id.category_id:
                raise ValidationError(_(
                    "The unit of measure %(uom)s is not compatible with %(product)s.",
                    uom=line.product_uom_id.name, product=product.display_name))
            if line.lot_id:
                if line.lot_id.product_id != product:
                    raise ValidationError(_(
                        "Lot %(lot)s is not a lot of %(product)s.",
                        lot=line.lot_id.name, product=product.display_name))
                if product.tracking == 'serial' and float_compare(
                        line.product_uom_qty, 1, precision_rounding=line.product_uom_id.rounding) != 0:
                    raise ValidationError(_(
                        "A line with a specific serial number must have a quantity of 1."))

    def _check_transfer_is_draft(self):
        if any(transfer.state != 'draft' for transfer in self.transfer_id):
            raise UserError(_("Product lines can only be modified while the transfer is in draft."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_transfer_is_draft()
        lines.transfer_id._check_ict_permission('both')
        return lines

    def write(self, vals):
        if set(vals) - {'sequence'}:
            self._check_transfer_is_draft()
            self.transfer_id._check_ict_permission('both')
        return super().write(vals)

    def unlink(self):
        self._check_transfer_is_draft()
        if self.sudo().move_ids:
            raise UserError(_("Lines linked to stock moves cannot be deleted."))
        return super().unlink()
