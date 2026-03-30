from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FuelLog(models.Model):
    _name = "fleet.fuel.log"
    _description = "Fuel Log"
    _order = "name desc"  # Order by newest first

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle")
    date = fields.Date(string="Date", required=True)
    driver_id = fields.Many2one('hr.employee', string="Driver")
    fuel_quantity = fields.Float(string="Fuel Quantity (Liters)", required=True)
    unit_price = fields.Float(string="Unit Price", required=True)
    total_cost = fields.Float(string="Total Cost", compute="_compute_total_cost", store=True)
    supplier_id = fields.Many2one(
    'res.partner',
    string="Supplier / Fuel Station",
    domain="[('supplier_rank','>',0)]"  # Only partners marked as suppliers
    )
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    notes = fields.Text(string="Notes")
    vendor_bill_id = fields.Many2one('account.move', string="Vendor Bill", readonly=True)

    # Add payment status field
    vendor_bill_payment_status = fields.Selection(
        string="Vendor Bill Payment Status",
        selection=[
            ('not_paid', 'Not Paid'),
            ('in_payment', 'In Payment'),
            ('paid', 'Paid')
        ],
        compute='_compute_vendor_bill_payment_status',
        store=True
    )

    @api.depends('vendor_bill_id.payment_state')
    def _compute_vendor_bill_payment_status(self):
        for record in self:
            if record.vendor_bill_id:
                record.vendor_bill_payment_status = record.vendor_bill_id.payment_state
            else:
                record.vendor_bill_payment_status = 'not_paid'


    @api.depends('fuel_quantity', 'unit_price')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.fuel_quantity * record.unit_price

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fleet.fuel.log') or _('New')
        return super(FuelLog, self).create(vals)


    def action_create_vendor_bill(self):
        """Create a vendor bill from the fuel log."""
        self.ensure_one()

        if not self.supplier_id:
            raise UserError(_("Please select a supplier before creating a vendor bill."))

        # Prevent duplication
        if self.vendor_bill_id:
            raise UserError(_("A vendor bill has already been created for this fuel log."))

        invoice_line_vals = {
            'name': f'Fuel for {self.vehicle_id.name}',
            'quantity': self.fuel_quantity,
            'price_unit': self.unit_price,
        }

        # Add analytic distribution if analytic account is set
        if self.analytic_account_id:
            invoice_line_vals['analytic_distribution'] = {self.analytic_account_id.id: 100.0}

        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.supplier_id.id,
            'invoice_date': self.date,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
        }

        # Create the vendor bill
        bill = self.env['account.move'].create(bill_vals)
        self.vendor_bill_id = bill.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bill',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
        }