from odoo import _, api, models
from odoo.exceptions import UserError

# A purchase order is frozen as soon as it is submitted for approval or confirmed.
GW_PO_LOCKED_STATES = ('to approve', 'purchase', 'done')

GW_PO_PROTECTED_FIELDS = {
    'partner_id', 'partner_ref', 'currency_id', 'date_order', 'date_planned', 'order_line',
    'payment_term_id', 'fiscal_position_id', 'incoterm_id', 'incoterm_location',
    'picking_type_id', 'dest_address_id', 'user_id', 'notes', 'company_id', 'origin',
}
GW_PO_LINE_PROTECTED_FIELDS = {
    'product_id', 'name', 'product_qty', 'product_uom', 'price_unit', 'taxes_id', 'discount',
    'date_planned', 'analytic_distribution', 'order_id', 'display_type',
}


def _gw_locked_error(orders):
    return UserError(_(
        "The purchase order(s) %(orders)s are submitted/confirmed and can no longer be modified, "
        "not even by an administrator. Cancel the order and set it back to draft to amend it.",
        orders=", ".join(orders.mapped('name')),
    ))


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def write(self, vals):
        # env.su: internal processes (procurement, portal date updates...) are not restricted.
        if not self.env.su and GW_PO_PROTECTED_FIELDS.intersection(vals):
            locked = self.filtered(lambda o: o.state in GW_PO_LOCKED_STATES)
            if locked:
                raise _gw_locked_error(locked)
        return super().write(vals)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            lock = "state in %s" % (GW_PO_LOCKED_STATES,)
            # Top-level fields only: the order lines become read-only through their one2many.
            for node in arch.xpath("//field[not(ancestor::field)]"):
                if node.get('name') == 'state':
                    continue
                current = (node.get('readonly') or '').strip()
                if current in ('1', 'True', 'true'):
                    continue
                node.set('readonly', f"({current}) or {lock}" if current else lock)
        return arch, view


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _gw_check_order_unlocked(self, orders):
        if self.env.su:
            return
        locked = orders.filtered(lambda o: o.state in GW_PO_LOCKED_STATES)
        if locked:
            raise _gw_locked_error(locked)

    @api.model_create_multi
    def create(self, vals_list):
        order_ids = [vals['order_id'] for vals in vals_list if vals.get('order_id')]
        self._gw_check_order_unlocked(self.env['purchase.order'].browse(order_ids))
        return super().create(vals_list)

    def write(self, vals):
        if GW_PO_LINE_PROTECTED_FIELDS.intersection(vals):
            self._gw_check_order_unlocked(self.order_id)
        return super().write(vals)

    def unlink(self):
        self._gw_check_order_unlocked(self.order_id)
        return super().unlink()
