from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    brand_id = fields.Many2one('product.brand', string='Brand')


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Product Brand'

    name = fields.Char(string="Name", required=True)
    brand_image = fields.Binary(string="Brand Image")
    member_ids = fields.One2many('product.template', 'brand_id', string="Products")
    product_count = fields.Integer(string='Product Count', compute='_compute_product_count', store=True)

    @api.depends('member_ids')
    def _compute_product_count(self):
        for brand in self:
            brand.product_count = len(brand.member_ids)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    brand_id = fields.Many2one(
        related='product_id.brand_id',
        string='Brand',
        store=True,
        readonly=True
    )
