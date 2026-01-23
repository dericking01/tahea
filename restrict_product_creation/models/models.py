from odoo import models, api
from odoo.exceptions import AccessError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('restrict_product_creation.group_product_create'):
            raise AccessError("You are not allowed to create products.")
        return super().create(vals_list)
