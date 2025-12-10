from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Add required attribute to existing fields through inheritance
    street = fields.Char(required=False)  # We'll handle validation in constraints
    city = fields.Char(required=False)    # We'll handle validation in constraints
    country_id = fields.Many2one('res.country', required=False)  # We'll handle validation in constraints
    
    @api.constrains('street', 'city', 'country_id', 'company_type')
    def _check_vendor_address_fields(self):
        """Validate that vendors have complete address information."""
        for partner in self:
            if partner.company_type == 'company' and partner.supplier_rank > 0:
                # This is a vendor (supplier)
                if not partner.street:
                    raise ValidationError(_("Street field is required for vendors."))
                if not partner.city:
                    raise ValidationError(_("City field is required for vendors."))
                if not partner.country_id:
                    raise ValidationError(_("Country field is required for vendors."))
    
    @api.model
    def create(self, vals):
        """Override create to enforce address validation for vendors."""
        partner = super().create(vals)
        # Trigger validation for new vendors
        if partner.company_type == 'company' and partner.supplier_rank > 0:
            partner._check_vendor_address_fields()
        return partner
    
    def write(self, vals):
        """Override write to enforce address validation when converting to vendor."""
        # Check if we're changing to vendor or updating vendor address
        result = super().write(vals)
        for partner in self:
            if partner.company_type == 'company' and partner.supplier_rank > 0:
                partner._check_vendor_address_fields()
        return result
    
    @api.onchange('company_type', 'supplier_rank', 'street', 'city', 'country_id')
    def _onchange_address_fields(self):
        """Show warning when vendor address is incomplete."""
        for partner in self:
            if partner.company_type == 'company' and partner.supplier_rank > 0:
                warnings = []
                if not partner.street:
                    warnings.append(_("Street is required"))
                if not partner.city:
                    warnings.append(_("City is required"))
                if not partner.country_id:
                    warnings.append(_("Country is required"))
                
                if warnings:
                    return {
                        'warning': {
                            'title': _("Missing Address Information"),
                            'message': '\n'.join(warnings)
                        }
                    }