from odoo import models, fields

class StockLedgerLine(models.TransientModel):
    """
    Transient model for displaying row-by-row stock movement history 
    and running balance for a specific product.
    """
    _name = 'stock.ledger.line'
    _description = 'Stock Ledger Line'
    _order = 'date asc, id asc'

    product_id = fields.Many2one('product.product', string="Product")
    date = fields.Datetime(string="Date")
    from_location = fields.Many2one('stock.location', string="From")
    from_warehouse = fields.Many2one('stock.warehouse', string="From Warehouse", related='from_location.warehouse_id', store=True)
    to_location = fields.Many2one('stock.location', string="To")
    to_warehouse = fields.Many2one('stock.warehouse', string="To Warehouse", related='to_location.warehouse_id', store=True)
    in_qty = fields.Float(string="Incoming")
    out_qty = fields.Float(string="Outgoing")

    transaction_type = fields.Selection([
        ('opening', 'OPENING BALANCE'),
        ('in', 'IN'),
        ('out', 'OUT'),
        ('internal', 'INTERNAL')
    ], string="Type")
    balance = fields.Float(string="Balance")
    location_balances_html = fields.Html(string="Balance per location")