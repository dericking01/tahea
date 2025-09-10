from odoo import fields, models, _
from odoo.exceptions import UserError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    internal_ref_sequence_id = fields.Many2one('ir.sequence', string='Internal Reference Sequence')
    automatic_ref_activated = fields.Boolean(string='Automatic Reference Activated', compute='_compute_automatic_ref_activated')

    def _compute_automatic_ref_activated(self):
        """
        This field in use in views to make the internal reference readonly.
        """
        for category in self:
            category.automatic_ref_activated = self.env['ir.config_parameter'].sudo().get_param('activate.automatic.product.ref', False)

    def get_sequence_for_internal_ref(self):
        """
        Travel among categories from bottom to top.
        Return the first sequence found.
        """
        self.ensure_one()
        current_categ = self
        sequence = self.env['ir.sequence']
        while current_categ and not sequence:
            sequence = current_categ.internal_ref_sequence_id
            current_categ = current_categ.parent_id
        if not sequence:
            raise UserError(_("Please set a sequence on this product's category or on one of its parent categories."))
        return sequence
