# -*- coding: utf-8 -*-
from odoo import api, fields, models

PROPERTY_CATEGORIES = [
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('industrial', 'Industrial'),
    ('hospitality', 'Hospitality'),
    ('mixed', 'Mixed-use'),
    ('land', 'Land'),
    ('special', 'Special Purpose'),
]


class ReAreaUnit(models.Model):
    _name = 're.area.unit'
    _description = 'Area Unit of Measure'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    factor_to_sqm = fields.Float('Square metres per unit', digits=(16, 6), required=True, default=1.0)
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Area unit code must be unique.')]

    def _to_sqm(self, value):
        self.ensure_one()
        return (value or 0.0) * (self.factor_to_sqm or 0.0)

    @api.model
    def _default_unit(self):
        return self.env.ref('real_estate_lifecycle.area_unit_sqm', raise_if_not_found=False)


class RePropertyType(models.Model):
    _name = 're.property.type'
    _description = 'Property Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    category = fields.Selection(PROPERTY_CATEGORIES, required=True, default='residential')
    is_land = fields.Boolean('Land / Plot Type',
                             help='Land properties are managed as plots without buildings/floors.')
    active = fields.Boolean(default=True)
    description = fields.Text()


class ReLeaseType(models.Model):
    _name = 're.lease.type'
    _description = 'Lease Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'),
        ('land', 'Land'), ('short_term', 'Short-term'), ('other', 'Other')], required=True, default='residential')
    default_billing_frequency = fields.Selection([
        ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('semi_annual', 'Semi-annual'), ('annual', 'Annual')],
        default='monthly')
    default_notice_days = fields.Integer('Default Notice Period (days)', default=90)
    default_deposit_months = fields.Float('Default Deposit (months of rent)', default=1.0)
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', 'Default Fiscal Position', company_dependent=True,
        help='Tax treatment differs per lease type (e.g. residential vs commercial). Configure the fiscal '
             'position in Accounting; nothing is hardcoded here.')
    active = fields.Boolean(default=True)


class ReAssetCategory(models.Model):
    _name = 're.asset.category'
    _description = 'Building Equipment Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    expected_life_years = fields.Float('Expected Useful Life (years)', default=15)
    default_criticality = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium')
    replacement_threshold_pct = fields.Float(
        'Replacement Review Threshold (%)', default=60.0,
        help='When cumulative repair cost reaches this % of the estimated replacement cost, '
             'the asset is flagged for a replacement review.')
    active = fields.Boolean(default=True)


class ReServiceCategory(models.Model):
    _name = 're.service.category'
    _description = 'Contractor Service Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)


class ReMaintenanceCategory(models.Model):
    _name = 're.maintenance.category'
    _description = 'Maintenance Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    service_category_id = fields.Many2one('re.service.category', 'Contractor Service Category')
    default_priority = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent')], default='1')
    target_days = fields.Integer('Target Resolution (days)', default=7)
    active = fields.Boolean(default=True)


class ReComplaintCategory(models.Model):
    _name = 're.complaint.category'
    _description = 'Tenant Request / Complaint Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    maintenance_category_id = fields.Many2one('re.maintenance.category')
    is_building_wide = fields.Boolean(
        'Can be a shared building issue', default=True,
        help='Complaints in this category are clustered per building to identify shared issues '
             '(e.g. water supply affecting many tenants).')
    active = fields.Boolean(default=True)
