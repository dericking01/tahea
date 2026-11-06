from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    # copy=True so that backorder splits, native returns and push moves stay
    # attached to the transfer line they originate from.
    intercompany_line_id = fields.Many2one(
        'intercompany.stock.transfer.line', 'Inter-Company Transfer Line',
        index='btree_not_null', readonly=True, copy=True, ondelete='restrict')
