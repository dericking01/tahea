from odoo import models, fields
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    manual_stock_journal_id = fields.Many2one(
        'account.move',
        string='Stock Expense Journal',
        readonly=True,
        copy=False
    )

    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        required=False
    )

    analytic_precision = fields.Integer(
        string="Analytic Precision",
        default=2
    )

    def action_create_manual_stock_journal(self):
        # self.ensure_one()

        # Prevent duplicate creation
        # if self.manual_stock_journal_id:
        #     raise UserError("COGS has already been created for this Delivery Order.")

        # Only for Delivery Orders
        if self.picking_type_id.code != 'outgoing':
            raise UserError("This action is only applicable to Delivery Orders.")

        # Only after validation
        if self.state != 'done':
            raise UserError("Please validate the Delivery Order first.")

        # if not self.analytic_distribution:
        #     raise UserError("Please set Analytic Distribution before creating the journal entry.")

        # Find General Journal
        journal = self.env['account.journal'].search(
            [('type', '=', 'general')],
            limit=1
        )

        if not journal:
            raise UserError("No General Journal found. Please create one.")

        move_lines_vals = []

        # Loop through stock moves
        for move in self.move_ids_without_package:
            product = move.product_id
            categ = product.categ_id

            stock_valuation_acct = categ.property_stock_valuation_account_id
            expense_acct = categ.property_account_expense_categ_id

            if not stock_valuation_acct:
                raise UserError(
                    f"Stock Valuation Account missing for category: {categ.name}"
                )

            if not expense_acct:
                raise UserError(
                    f"Expense Account missing for category: {categ.name}"
                )

            # Loop move lines
            for line in move.move_line_ids:
                qty = line.quantity

                if qty <= 0:
                    continue

                value = qty * product.standard_price

                # Debit Expense (COGS)
                move_lines_vals.append((0, 0, {
                    'name': f"Expense - {product.display_name}",
                    'account_id': expense_acct.id,
                    'debit': value,
                    'credit': 0,
                    'analytic_distribution': self.analytic_distribution,
                }))

                # Credit Stock Valuation
                move_lines_vals.append((0, 0, {
                    'name': f"Stock Valuation - {product.display_name}",
                    'account_id': stock_valuation_acct.id,
                    'credit': value,
                    'debit': 0,
                }))

        if not move_lines_vals:
            raise UserError("No quantities found to create journal entry.")
        
        if not move_lines_vals:
            raise UserError("No quantities found to create journal entry.")
        
        # Use delivery order's effective date for accounting date
        accounting_date = self.date_done

        # Create Journal Entry
        account_move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': accounting_date,
            'ref': f"Delivery Order: {self.name}",
            'line_ids': move_lines_vals,
        })

        # Post the entry
        account_move.action_post()

        # Link Journal Entry to Delivery Order
        self.manual_stock_journal_id = account_move.id

        # Open Journal Entry
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': account_move.id,
        }