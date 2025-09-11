import re
from odoo import models, fields, api
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    bill_id = fields.Many2one('account.move', string='Vendor Bill', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')

    def action_create_vendor_bill(self):
        self.ensure_one()

        # 🔒 Restrict creating another bill
        if self.bill_id:
            raise UserError(
                f"A vendor bill has already been created for this approval request: {self.bill_id.name}. "
                "You cannot create another one."
            )

        # ✅ Get Vendor directly from partner_id (contact)
        vendor = self.partner_id
        if not vendor:
            raise UserError("This approval request has no Contact (Vendor) assigned.")

        # ✅ Ensure analytic account is selected before creating a bill
        if not self.analytic_account_id:
            raise UserError("Please select an Analytic Account before creating the Vendor Bill.")

        # Use approval reason if available, otherwise fallback to record name
        raw_description = self.reason or self.name

        # Remove HTML tags for bill line
        line_description = re.sub(r'<[^>]+>', '', raw_description).strip()

        # Create Vendor Bill
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.today(),
            'name': '/',                   # Auto sequence
            'ref': self.name,              # Approval request reference
            'invoice_origin': self.name,   # Traceability
            'invoice_line_ids': [(0, 0, {
                'name': line_description,
                'quantity': 1,
                'price_unit': self.amount,
                'analytic_distribution': {self.analytic_account_id.id: 100.0},   # ✅ Analytic Account added here
            })],
        })

        # Link bill to approval request
        self.bill_id = bill.id

        # Open created bill
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
        }