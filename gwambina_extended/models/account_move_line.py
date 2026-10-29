from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    po_original_qty = fields.Float(
        string='Original PO Bill Quantity',
        digits='Product Unit of Measure',
        copy=False,
        readonly=True,
        help="Quantity of the line when it was created from the purchase order. "
             "On a draft vendor bill the quantity can be lowered but never raised above this value.",
    )
    po_qty_locked = fields.Boolean(compute='_compute_po_qty_locked')

    @api.depends('purchase_line_id', 'move_id.move_type')
    def _compute_po_qty_locked(self):
        for line in self:
            line.po_qty_locked = bool(line.purchase_line_id) and line.move_id.move_type == 'in_invoice'

    def _gw_po_controlled_lines(self):
        return self.filtered(lambda l: (
            l.purchase_line_id
            and l.move_id.move_type == 'in_invoice'
            and l.display_type == 'product'
            and not l.is_downpayment
        ))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(AccountMoveLine, self.with_context(gw_skip_po_bill_check=True)).create(vals_list)
        lines = lines.with_env(self.env)
        po_lines = lines.filtered('purchase_line_id')
        for line in po_lines:
            line.po_original_qty = line.quantity
        po_lines._gw_check_po_billable_qty()
        po_lines._gw_check_po_bill_line()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'purchase_line_id' in vals:
            for line in self.filtered('purchase_line_id'):
                line.po_original_qty = line.quantity
        return res

    def _gw_check_po_billable_qty(self):
        """ A new bill line linked to a PO cannot bill more than what is still billable on the
        PO line (received quantity or ordered quantity, depending on the control policy). """
        errors = []
        for line in self._gw_po_controlled_lines():
            pol = line.purchase_line_id
            if pol.order_id.state not in ('purchase', 'done'):
                continue
            if float_compare(pol.qty_to_invoice, 0.0, precision_rounding=pol.product_uom.rounding) < 0:
                billable = pol.qty_to_invoice + line.product_uom_id._compute_quantity(line.quantity, pol.product_uom)
                errors.append(_(
                    "- %(product)s: %(qty)s %(uom)s entered, only %(billable)s %(pol_uom)s left to bill on %(po)s",
                    product=line.product_id.display_name or line.name,
                    qty=line.quantity, uom=line.product_uom_id.name,
                    billable=max(billable, 0.0), pol_uom=pol.product_uom.name,
                    po=pol.order_id.name,
                ))
        if errors:
            raise ValidationError(
                _("You cannot bill more than the quantity received/ordered on the purchase order:\n%s",
                  "\n".join(errors)))

    @api.constrains('quantity', 'product_uom_id')
    def _gw_check_po_bill_line(self):
        if self.env.context.get('gw_skip_po_bill_check'):
            return
        qty_errors = []
        uom_errors = []
        for line in self._gw_po_controlled_lines().filtered(lambda l: l.move_id.state == 'draft'):
            if line.product_uom_id != line.purchase_line_id.product_uom:
                uom_errors.append(_(
                    "- %(product)s: the unit of measure must stay %(uom)s",
                    product=line.product_id.display_name or line.name,
                    uom=line.purchase_line_id.product_uom.name,
                ))
            rounding = line.product_uom_id.rounding or 0.01
            if float_compare(line.quantity, line.po_original_qty, precision_rounding=rounding) > 0:
                qty_errors.append(_(
                    "- %(product)s: %(qty)s entered, maximum allowed is %(original)s (%(po)s)",
                    product=line.product_id.display_name or line.name,
                    qty=line.quantity,
                    original=line.po_original_qty,
                    po=line.purchase_line_id.order_id.name,
                ))
        message = []
        if qty_errors:
            message.append(_(
                "The quantity of a vendor bill line created from a purchase order cannot exceed its original quantity:\n%s",
                "\n".join(qty_errors)))
        if uom_errors:
            message.append(_(
                "The unit of measure of a vendor bill line created from a purchase order cannot be changed:\n%s",
                "\n".join(uom_errors)))
        if message:
            raise ValidationError("\n\n".join(message))
