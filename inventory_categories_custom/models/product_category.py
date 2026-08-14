from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True, 
        default=lambda self: self.env.company,
        index=True,
        help="The company related to this category."
    )