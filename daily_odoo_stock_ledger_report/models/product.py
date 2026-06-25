from odoo import models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_stock_ledger(self):
        """
        Generate and display the stock ledger lines for the selected product
        based on the date range provided in the context.
        """
        self.ensure_one()
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')
        company_id = self.env.company.id

        # Delete only the current user's temporary lines to prevent global wipe
        self.env['stock.ledger.line'].search([('create_uid', '=', self.env.uid)]).unlink()

        opening_qty = 0

        # Calculate opening balance from all DONE moves prior to date_from
        opening_moves = self.env['stock.move.line'].search([
            ('product_id', '=', self.id),
            ('date', '<', date_from),
            ('state', '=', 'done'),
            ('company_id', '=', company_id)
        ])

        for move in opening_moves:
            if move.location_dest_id.usage == 'internal':
                opening_qty += move.quantity
            if move.location_id.usage == 'internal':
                opening_qty -= move.quantity

        balance = opening_qty

        # Create an opening balance line for clear visibility
        self.env['stock.ledger.line'].create({
            'product_id': self.id,
            'date': date_from + " 00:00:00" if isinstance(date_from, str) else date_from,
            'in_qty': 0,
            'out_qty': 0,
            'transaction_type': 'opening',
            'balance': balance,
        })

        # Fetch lines within the reporting period
        moves = self.env['stock.move.line'].search([
            ('product_id', '=', self.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'done'),
            ('company_id', '=', company_id)
        ], order='date asc, id asc')

        for move in moves:
            in_qty = 0
            out_qty = 0
            transaction_type = False
            
            src_internal = move.location_id.usage == 'internal'
            dest_internal = move.location_dest_id.usage == 'internal'

            if src_internal and dest_internal:
                # Internal transfer - does not affect net balance
                in_qty = move.quantity
                out_qty = move.quantity
                transaction_type = 'internal'
            elif dest_internal:
                # Incoming stock
                in_qty = move.quantity
                balance += in_qty
                transaction_type = 'in'
            elif src_internal:
                # Outgoing stock
                out_qty = move.quantity
                balance -= out_qty
                transaction_type = 'out'
            else:
                # E.g., transit to transit, meaning no internal stock is touched
                continue

            self.env['stock.ledger.line'].create({
                'product_id': self.id,
                'date': move.date,
                'from_location': move.location_id.id,
                'to_location': move.location_dest_id.id,
                'in_qty': in_qty,
                'out_qty': out_qty,
                'transaction_type': transaction_type,
                'balance': balance,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Ledger',
            'res_model': 'stock.ledger.line',
            'view_mode': 'list',
            'target': 'current',
            'domain': [('create_uid', '=', self.env.uid)],
        }