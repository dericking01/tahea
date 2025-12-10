from odoo import models, fields, api
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    manual_stock_journal_id = fields.Many2one(
        'account.move',
        string='Stock Expense Journal',
        readonly=True,
        copy=False
    )

    def action_create_manual_stock_journal(self):
        self.ensure_one()

        # 🚫 Prevent double creation
        if self.manual_stock_journal_id:
            raise UserError("COGS has already been created for this Delivery Order.")

        # Only for deliveries
        if self.picking_type_id.code != 'outgoing':
            raise UserError("This action is only applicable to Delivery Orders.")

        # Only after validation
        if self.state != 'done':
            raise UserError("Please validate the Delivery Order first.")

        # Get General Journal
        journal = self.env['account.journal'].search(
            [('type', '=', 'general')],
            limit=1
        )
        if not journal:
            raise UserError("No general journal found. Please create one first.")

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

            # Move Lines (Odoo 18 uses line.quantity)
            for line in move.move_line_ids:
                qty = line.quantity
                if qty <= 0:
                    continue

                value = qty * product.standard_price

                # DEBIT: Expense
                move_lines_vals.append((0, 0, {
                    'name': f"Expense - {product.display_name}",
                    'account_id': expense_acct.id,
                    'debit': value,
                    'credit': 0,
                }))

                # CREDIT: Stock Valuation
                move_lines_vals.append((0, 0, {
                    'name': f"Stock Valuation - {product.display_name}",
                    'account_id': stock_valuation_acct.id,
                    'credit': value,
                    'debit': 0,
                }))

        if not move_lines_vals:
            raise UserError("No quantities found to create journal entry.")

        # Create Journal Entry
        account_move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'ref': f"Delivery Order: {self.name}",
            'line_ids': move_lines_vals,
        })

        # Post it
        account_move.action_post()

        # Link journal entry to delivery
        self.manual_stock_journal_id = account_move.id

        # Open JE form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': account_move.id,
        }
