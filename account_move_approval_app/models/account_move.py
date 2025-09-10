from odoo import models, fields, api, _ # type: ignore
from odoo.exceptions import UserError, ValidationError # type: ignore

class AccountMove(models.Model):
    _inherit = "account.move"

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain=[],  # Empty domain to show all journals
        check_company=True,
    )

    state = fields.Selection(
        selection_add=[
            ('submited', 'Submitted'),  # Fixed typo in display value
            ('approved', 'Approved'),
            ('validate', 'Validated')
        ],
        ondelete={
            'submited': 'set default',  # Define what happens when module is uninstalled
            'approved': 'set default',
            'validate': 'set default'
        }
    )
    created_by = fields.Many2one('res.users', index=True, string="Created By")
    approved_by = fields.Many2one('res.users', index=True, string="Approved By")
    validated_by = fields.Many2one('res.users', index=True, string="Validated By")

    def button_submit_move(self):
        for record in self:
            record.state = 'submited'

    def button_approve_move(self):
        if self.user_has_groups('account_move_approval_app.group_finance_manager'):
            self.approved_by = self.env.user
            self.state = 'approved'
        else:
            self.approved_by = False

    def button_validate_move(self):
        if self.user_has_groups('account_move_approval_app.group_director'):
            self.validated_by = self.env.user
            self.state = 'validate'
        else:
            self.validated_by = False

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # Add these fields to match account.move fields
    approved_by = fields.Many2one('res.users', string="Approved By")
    validated_by = fields.Many2one('res.users', string="Validated By")
    created_by = fields.Many2one('res.users', string="Created By")

    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string="Analytic Tags")
    invoice_id = fields.Many2one('account.move', string="Account Move")
    effective_date = fields.Date("Effective Date")
    bank_reference = fields.Char("Bank reference")
    cheque_reference = fields.Char("Cheque Reference")

    @api.model
    def default_get(self, default_fields):
        rec = super(AccountPayment, self).default_get(default_fields)
        active_id = self._context.get('active_id')
        if not active_id:
            return rec
            
        invoice_id = self.env['account.move'].browse(active_id)
        line_ids = self.env['account.move.line'].search([('id','in',invoice_id.line_ids.ids)], limit=1)
        analytic_account_id = line_ids.mapped('analytic_account_id')
        analytic_tag_ids = [tag.id for tag in invoice_id.line_ids.mapped('analytic_tag_ids')]
        
        rec.update({
            'invoice_id': invoice_id.id,
            'analytic_account_id': analytic_account_id.id if analytic_account_id else False,
            'analytic_tag_ids': [(6,0,analytic_tag_ids)] if analytic_tag_ids else False
        })
        return rec

    def _prepare_payment_moves(self):
        payment_moves = super(AccountPayment, self)._prepare_payment_moves()
        tags = [tag.id for tag in self.analytic_tag_ids]
        
        if self.analytic_account_id or self.analytic_tag_ids:
            for move_line in payment_moves[0]['line_ids']:
                if self.analytic_account_id:
                    move_line[2].update({
                        'analytic_account_id': self.analytic_account_id.id
                    })
                if self.analytic_tag_ids:
                    move_line[2].update({
                        'analytic_tag_ids': [(6,0,tags)]
                    })
        
        if self.invoice_id:
            payment_moves[0].update({
                'narration': self.invoice_id.narration
            })
            
        return payment_moves

    def action_post(self):  # Changed from post() to action_post()
        """ Create the journal items for the payment and update the payment's state to 'posted'."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only a draft payment can be posted."))

            if any(inv.state != 'posted' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # keep the name in case of a payment reset to draft
            if not rec.name:
                # Use the right sequence to set the name
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].next_by_code(sequence_code, sequence_date=rec.payment_date)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            moves = self.env['account.move'].with_context(default_move_type='entry').create(rec._prepare_payment_moves())
            
            # Handle validation state
            if rec.invoice_id.move_type in ['in_invoice', 'in_refund']:  # Changed from type to move_type
                if moves.state == 'validate':
                    moves._post()  # Changed from post() to _post()
                else:
                    moves.state = 'submited'
            else:
                moves._post()  # Changed from post() to _post()

            # Update analytic data
            account_move = self.env['account.move'].browse(self._context.get('active_id'))
            tags = [tag.id for tag in self.analytic_tag_ids]
            for invoice_line in account_move.invoice_line_ids:
                if self.analytic_account_id:
                    invoice_line.write({
                        'analytic_account_id': self.analytic_account_id.id
                    })
                if self.analytic_tag_ids:
                    invoice_line.write({
                        'analytic_tag_ids': [(6,0,tags)]
                    })

            # Update the state / move before performing any reconciliation.
            move_name = self._get_move_name_transfer_separator().join(moves.mapped('name'))
            rec.write({'state': 'posted', 'move_name': move_name})

            if rec.payment_type in ('inbound', 'outbound'):
                # ==== 'inbound' / 'outbound' ====
                if rec.invoice_ids:
                    (moves[0] + rec.invoice_ids).line_ids \
                        .filtered(lambda line: not line.reconciled and line.account_id == rec.destination_account_id and not (line.account_id == line.payment_id.writeoff_account_id and line.name == line.payment_id.writeoff_label))\
                        .reconcile()
            elif rec.payment_type == 'transfer':
                # ==== 'transfer' ====
                moves.mapped('line_ids')\
                    .filtered(lambda line: line.account_id == rec.company_id.transfer_account_id)\
                    .reconcile()

        return True