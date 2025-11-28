from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    # We'll inherit the existing button_confirm method but won't modify it
    # The visibility change will be handled in the view XML