from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    automatic_ref_activated = fields.Boolean(string='Automatic Reference Activated', compute='_compute_automatic_ref_activated')

    def _compute_automatic_ref_activated(self):
        """
        This field in use in views to make the internal reference readonly.
        """
        for product in self:
            product.automatic_ref_activated = self.env['ir.config_parameter'].sudo().get_param('activate.automatic.product.ref', False)

    @api.constrains('default_code')
    def unique_default_code(self):
        for product in self.filtered(lambda p: p.default_code):
            product_with_same_code = self.env['product.template'].search([('default_code', '=', product.default_code), ('id', '!=', product.id)])
            if product_with_same_code:
                raise UserError(_('These product templates: %s, %s have the same default code') % (product.display_name, product_with_same_code.display_name))

    @api.model_create_multi
    def create(self, val_list):
        """
        Override create
        If the parameter 'Activate Automatic Product Internal Reference' of the Inventory settings is activated then
        Odoo create and populate the internal reference of products by himself.
        If somebody try to set the Internal reference during creation Odoo will throw back an error.
        """
        automatic_ref_activated = self.env['ir.config_parameter'].sudo().get_param('activate.automatic.product.ref', False)
        if automatic_ref_activated and not self.env.context.get('product_ref', False):
            for values in val_list:
                if 'default_code' in values and values.get('default_code', False):
                    raise UserError(_("Sorry, you cannot set an Internal Reference. Odoo set it by himself!"))
                defaults = self.default_get(['categ_id'])
                categ_id = values.get('categ_id') or defaults.get('categ_id')
                category = self.env['product.category'].browse(categ_id)
                sequence = category.get_sequence_for_internal_ref()
                values['default_code'] = sequence.next_by_id()
        return super(ProductTemplate, self.with_context(product_ref=True)).create(val_list)

    def write(self, vals):
        """
        Block the possibility to modify the internal reference.
        """
        automatic_ref_activated = self.env['ir.config_parameter'].sudo().get_param('activate.automatic.product.ref', False)
        if not self.env.context.get('product_ref', False) and not self.env.context.get('force_default_code', False) and automatic_ref_activated and 'default_code' in vals:
            raise UserError(_("Sorry, you cannot modify the Internal Reference of a Product."))
        return super().write(vals)
