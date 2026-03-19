# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def action_create_vendor_bill(self):
        # Call original logic
        action = super().action_create_vendor_bill()

        # After bill is created, attach approval info
        for record in self:
            if record.bill_id:
                record.bill_id.write({
                    'approval_id': record.id,
                    'approved_amount': record.amount,  # from your approval.amount field
                })

        return action

class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_id = fields.Many2one(
        'approval.request',
        string="Approval Reference",
        copy=False
    )

    approved_amount = fields.Monetary(
        string="Approved Amount",
        currency_field='currency_id',
        copy=False
    )

    def action_post(self):
        for move in self:
            # Apply only to Vendor Bills linked to approvals
            if move.move_type == 'in_invoice' and move.approval_id:
                if move.amount_total > move.approved_amount:
                    raise UserError(
                        f"❌ Vendor Bill exceeds approved amount.\n\n"
                        f"Approved: {move.approved_amount}\n"
                        f"Bill: {move.amount_total}\n"
                        f"Please adjust the bill to match the approved amount."
                    )

        return super(AccountMove, self).action_post()