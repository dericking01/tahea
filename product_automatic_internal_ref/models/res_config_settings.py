from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activate_automatic_product_ref = fields.Boolean(string='Activate Automatic Product Internal Reference',
                                                    help='When this parameter is activated, the internal reference of products will become read-only.\n'
                                                         'During the creation of a new product, Odoo will automatically populate its internal reference.\n'
                                                         'You can configure an Odoo sequence for product categories, allowing each category to have a specific sequence.')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'activate_automatic_product_ref': self.env['ir.config_parameter'].sudo().get_param('activate.automatic.product.ref', False),
        })
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].set_param('activate.automatic.product.ref', self.activate_automatic_product_ref)

    def add_sequence_on_product_without_any(self):
        """
        Allow to generate of internal reference for every product without one.
        """
        products = self.env['product.product'].search([('default_code', '=', False), ('product_tmpl_id.default_code', '!=', False)])
        products = products.with_context(force_default_code=True)
        products_tmpl = self.env['product.template'].search([('default_code', '=', False)])
        products_tmpl = products_tmpl.with_context(force_default_code=True)
        # Set an internal reference for every product template that do not have one.
        for tmpl in products_tmpl:
            sequence = tmpl.categ_id.get_sequence_for_internal_ref()
            tmpl.default_code = sequence.next_by_id()
            if len(tmpl.product_variant_ids) > 1:
                # Set an internal reference for variants of the template that do not have one.
                for variant in tmpl.product_variant_ids.filtered(lambda v: not v.default_code):
                    variant.default_code = sequence.next_by_id()
        # Set an internal reference for variant without one but that has a template with an internal reference
        for product in products:
            sequence = product.categ_id.get_sequence_for_internal_ref()
            product.default_code = sequence.next_by_id()
