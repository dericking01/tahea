from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    gw_receipt_confirmation = fields.Boolean(
        string='Receipt Confirmation by Destination',
        help="Internal transfers of this type are first dispatched to the transit location. "
             "The person in charge of the destination location then confirms the quantities "
             "physically received before they are added to the destination stock. "
             "Only applies when the destination location has persons in charge.",
    )
