from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPickingLine(models.Model):
    _inherit = 'stock.move'

    remaining_qty = fields.Float(
        string='Remaining Qty to Bill',
        compute='_compute_remaining_qty',
        store=False,
        help="Quantity of this item remaining to be billed"
    )

    is_remaining = fields.Boolean(
        string='Has Remaining',
        compute='_compute_is_remaining',
        store=False,
        help="True if this item has qty remaining to bill"
    )

    vendor_bill_ids_count = fields.Integer(
        string='Vendor Bills Count',
        compute='_compute_vendor_bill_count'
    )

    def _compute_vendor_bill_count(self):
        for picking in self:
            picking.vendor_bill_ids_count = len(picking.vendor_bill_ids.filtered(lambda b: b.state != 'cancel'))

    def _compute_remaining_qty(self):
        """Calculate remaining quantity for each line."""
        for line in self:

            remaining = line.quantity

            if line.picking_id:
                bills = self.env['account.move'].search([
                    ('picking_id', '=', line.picking_id.id),
                    ('move_type', '=', 'in_invoice'),
                    ('state', '!=', 'cancel')
                ])

                billed_qty = 0.0

                for bill in bills:
                    for bill_line in bill.invoice_line_ids:
                        if bill_line.product_id.id == line.product_id.id:
                            billed_qty += bill_line.quantity

                remaining = line.quantity - billed_qty

            line.remaining_qty = max(0.0, remaining)

    def _compute_is_remaining(self):
        """Check if this line has remaining quantity."""
        for line in self:
            line.is_remaining = line.remaining_qty > 0


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    vendor_bill_ids = fields.One2many(
        'account.move',
        'picking_id',
        string='Vendor Bills',
        readonly=True
    )

    is_fully_billed = fields.Boolean(
        string='Fully Billed',
        compute='_compute_is_fully_billed',
        store=False
    )

    remaining_to_bill = fields.Float(
        string='Remaining to Bill',
        compute='_compute_remaining_to_bill',
        store=False
    )

    has_remaining_items = fields.Boolean(
        string='Has Remaining Items',
        compute='_compute_has_remaining_items',
        store=False
    )

    # ------------------------------------------------------------
    # VIEW VENDOR BILLS
    # ------------------------------------------------------------

    def action_view_vendor_bill(self):
        self.ensure_one()

        bills = self.vendor_bill_ids.filtered(lambda b: b.state != 'cancel')

        if not bills:
            return False

        if len(bills) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': bills.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bills.ids)],
            'target': 'current',
        }

    # ------------------------------------------------------------
    # CHECK FULLY BILLED
    # ------------------------------------------------------------

    def _compute_is_fully_billed(self):
        for picking in self:

            billed_qty = {}
            received_qty = {}

            for move in picking.move_ids_without_package:
                if move.product_id:
                    received_qty[move.product_id.id] = (
                        received_qty.get(move.product_id.id, 0.0)
                        + move.quantity
                    )

            bills = picking.vendor_bill_ids.filtered(lambda b: b.state != 'cancel')

            for bill in bills:
                for line in bill.invoice_line_ids:
                    if line.product_id:
                        billed_qty[line.product_id.id] = (
                            billed_qty.get(line.product_id.id, 0.0)
                            + line.quantity
                        )

            fully_billed = True

            for product_id, qty in received_qty.items():
                if billed_qty.get(product_id, 0.0) < qty:
                    fully_billed = False
                    break

            picking.is_fully_billed = fully_billed

    # ------------------------------------------------------------
    # REMAINING TO BILL
    # ------------------------------------------------------------

    def _compute_remaining_to_bill(self):

        for picking in self:

            remaining = 0.0

            bills = picking.vendor_bill_ids.filtered(lambda b: b.state != 'cancel')

            for move in picking.move_ids_without_package:

                received_qty = move.quantity
                billed_qty = 0.0

                for bill in bills:
                    for line in bill.invoice_line_ids:
                        if line.product_id.id == move.product_id.id:
                            billed_qty += line.quantity

                remaining += (received_qty - billed_qty)

            picking.remaining_to_bill = max(0.0, remaining)

    # ------------------------------------------------------------
    # CHECK REMAINING ITEMS
    # ------------------------------------------------------------

    def _compute_has_remaining_items(self):

        for picking in self:

            bills = picking.vendor_bill_ids.filtered(lambda b: b.state != 'cancel')

            billed_qty = {}

            for bill in bills:
                for line in bill.invoice_line_ids:
                    if line.product_id:
                        billed_qty[line.product_id.id] = (
                            billed_qty.get(line.product_id.id, 0.0)
                            + line.quantity
                        )

            has_remaining = False

            for move in picking.move_ids_without_package:

                if move.product_id:

                    received = move.quantity
                    billed = billed_qty.get(move.product_id.id, 0.0)

                    if received > billed:
                        has_remaining = True
                        break

            picking.has_remaining_items = has_remaining

    # ------------------------------------------------------------
    # CREATE VENDOR BILL
    # ------------------------------------------------------------

    def action_create_vendor_bill(self):

        self.ensure_one()

        if not self.env.user.has_group('ask_grn_picking.group_grn_picking_user'):
            raise UserError(_("You are not allowed to create Vendor Bills from GRN."))

        if self.origin:
            raise UserError(
                _("This GRN was created from a source document (%s). "
                  "Please create the bill from the source document instead.") % self.origin
            )

        if not self.partner_id:
            raise UserError(_("Please set a Vendor on the GRN."))

        if self.state != 'done':
            raise UserError(_("GRN must be validated (Done) before creating a bill."))

        invoice_lines = []

        for move in self.move_ids_without_package:

            if move.quantity <= 0:
                continue

            invoice_lines.append((0, 0, {
                'product_id': move.product_id.id,
                'name': move.product_id.display_name,
                'quantity': move.quantity,
                'price_unit': move.product_id.standard_price,
            }))

        if not invoice_lines:
            raise UserError(_("No quantities available for billing."))

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'picking_id': self.id,
            'invoice_line_ids': invoice_lines,
        })

        # bill.message_post(
        #     body=_("Vendor Bill created from GRN: ") +
        #          f"<a href='#' data-oe-model='stock.picking' data-oe-id='{self.id}' "
        #          f"class='o_field_many2one_link'>{self.name}</a>"
        # )
        #
        # self.message_post(
        #     body=_("Vendor Bill created: ") +
        #          f"<a href='#' data-oe-model='account.move' data-oe-id='{bill.id}' "
        #          f"class='o_field_many2one_link'>{bill.name}</a>"
        # )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }

    # ------------------------------------------------------------
    # CREATE REMAINING BILL
    # ------------------------------------------------------------

    def action_create_remaining_bill(self):

        self.ensure_one()

        if not self.env.user.has_group('ask_grn_picking.group_grn_picking_user'):
            raise UserError(_("You are not allowed to create Vendor Bills from GRN."))

        if not self.partner_id:
            raise UserError(_("Please set a Vendor on the GRN."))

        if self.state != 'done':
            raise UserError(_("GRN must be validated before creating a bill."))

        bills = self.vendor_bill_ids.filtered(lambda b: b.state != 'cancel')

        if not bills:
            raise UserError(_("No initial bill exists. Create the full bill first."))

        invoice_lines = []

        for move in self.move_ids_without_package:

            if move.remaining_qty <= 0:
                continue

            invoice_lines.append((0, 0, {
                'product_id': move.product_id.id,
                'name': move.product_id.display_name,
                'quantity': move.remaining_qty,
                'price_unit': move.product_id.standard_price,
            }))

        if not invoice_lines:
            raise UserError(_("All items are already fully billed."))

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'picking_id': self.id,
            'invoice_line_ids': invoice_lines,
        })

        self.message_post(
            body=_("Remaining Bill created: ") +
                 f"<a href='#' data-oe-model='account.move' data-oe-id='{bill.id}' "
                 f"class='o_field_many2one_link'>{bill.name}</a>"
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Remaining Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }