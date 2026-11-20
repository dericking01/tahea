# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

TITLE_TYPES = [
    ('granted_ro', 'Granted Right of Occupancy (Certificate of Title)'),
    ('customary_ro', 'Customary Right of Occupancy (CCRO)'),
    ('residential_licence', 'Residential Licence'),
    ('offer_letter', 'Letter of Offer (title in process)'),
    ('freehold', 'Freehold'),
    ('leasehold', 'Leasehold / Sub-lease'),
    ('other', 'Other'),
]


class ReProperty(models.Model):
    _name = 're.property'
    _description = 'Property'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'code, name'
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char('Property Code', required=True, copy=False, tracking=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('re.property') or '/')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Registration'),
        ('active', 'Operational'),
        ('under_development', 'Under Development'),
        ('disposed', 'Disposed'),
    ], default='draft', required=True, tracking=True)
    property_type_id = fields.Many2one('re.property.type', 'Property Type', required=True, tracking=True)
    category = fields.Selection(related='property_type_id.category', store=True)
    is_land = fields.Boolean(related='property_type_id.is_land', store=True)
    portfolio_id = fields.Many2one('re.portfolio', 'Portfolio', tracking=True, check_company=True)

    # ---- Responsibility / ownership --------------------------------------------------
    company_id = fields.Many2one('res.company', 'Accounting Company', required=True, index=True,
                                 default=lambda self: self.env.company, tracking=True,
                                 help='The Odoo company in which this property is accounted for.')
    currency_id = fields.Many2one(related='company_id.currency_id')
    managing_partner_id = fields.Many2one('res.partner', 'Managing Company',
                                          help='Company that manages the property (may differ from owner).')
    manager_id = fields.Many2one('res.users', 'Property Manager', tracking=True,
                                 default=lambda self: self.env.user)
    user_ids = fields.Many2many('res.users', 're_property_user_rel', 'property_id', 'user_id',
                                string='Authorised Staff',
                                help='Restricted staff (property managers, leasing officers, technicians) '
                                     'can only access properties where they are the manager or listed here.')
    investor_user_ids = fields.Many2many('res.users', 're_property_investor_rel', 'property_id', 'user_id',
                                         string='Investor / Owner Users',
                                         help='Investor users with read-only access to this property.')
    ownership_ids = fields.One2many('re.property.ownership', 'property_id', 'Ownership History')
    legal_owner_id = fields.Many2one('res.partner', 'Current Legal Owner', compute='_compute_legal_owner',
                                     store=True)

    # ---- Location ---------------------------------------------------------------------
    street = fields.Char()
    street2 = fields.Char()
    ward = fields.Char()
    district = fields.Char()
    region = fields.Char(index=True)
    city = fields.Char()
    country_id = fields.Many2one('res.country', default=lambda self: self.env.company.country_id)
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))

    # ---- Acquisition / value ---------------------------------------------------------
    acquisition_date = fields.Date(tracking=True)
    purchase_price = fields.Monetary(tracking=True)
    acquisition_costs = fields.Monetary('Acquisition Costs (fees, stamp duty...)')
    valuation_ids = fields.One2many('re.property.valuation', 'property_id')
    current_valuation = fields.Monetary(compute='_compute_valuation', store=True)
    last_valuation_date = fields.Date(compute='_compute_valuation', store=True)

    # ---- Physical ---------------------------------------------------------------------
    land_area = fields.Float('Land Size')
    land_area_unit_id = fields.Many2one('re.area.unit', default=lambda self: self.env['re.area.unit']._default_unit())
    built_area = fields.Float('Gross Building Area')
    built_area_unit_id = fields.Many2one('re.area.unit', default=lambda self: self.env['re.area.unit']._default_unit())
    lettable_area_sqm = fields.Float('Total Lettable Area (m²)', compute='_compute_unit_stats', store=True)
    construction_date = fields.Date()
    condition = fields.Selection([
        ('new', 'New'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor'), ('derelict', 'Derelict')],
        default='good', tracking=True)
    description = fields.Html()

    # ---- Insurance --------------------------------------------------------------------
    insurer_id = fields.Many2one('res.partner', 'Insurer')
    insurance_policy = fields.Char('Policy Number')
    insured_value = fields.Monetary()
    insurance_expiry = fields.Date(tracking=True)

    # ---- Land title (Tanzania-ready, configurable) ------------------------------------
    title_type = fields.Selection(TITLE_TYPES, 'Title Type')
    title_number = fields.Char('Title / Certificate No.', tracking=True)
    plot_number = fields.Char('Plot No.')
    block_number = fields.Char('Block')
    survey_plan_number = fields.Char('Survey Plan No.')
    title_issue_date = fields.Date()
    title_term_years = fields.Integer('Term (years)', help='e.g. 33, 66 or 99 years for a granted right of occupancy.')
    title_expiry_date = fields.Date(compute='_compute_title_expiry', store=True, readonly=False)
    land_use = fields.Selection([
        ('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'),
        ('agricultural', 'Agricultural'), ('mixed', 'Mixed'), ('institutional', 'Institutional')])
    annual_land_rent = fields.Monetary('Annual Land Rent (payable)')
    encumbrance_ids = fields.One2many('re.land.encumbrance', 'property_id')

    # ---- Accounting dimensions -------------------------------------------------------
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', copy=False,
                                          readonly=True, check_company=False, index=True)

    # ---- Structure -------------------------------------------------------------------
    building_ids = fields.One2many('re.building', 'property_id')
    unit_ids = fields.One2many('re.unit', 'property_id')
    lease_ids = fields.One2many('re.lease', 'property_id')
    work_order_ids = fields.One2many('re.work.order', 'property_id')
    building_count = fields.Integer(compute='_compute_unit_stats', store=True)
    unit_count = fields.Integer('Lettable Units', compute='_compute_unit_stats', store=True)
    occupied_unit_count = fields.Integer(compute='_compute_unit_stats', store=True)
    vacant_unit_count = fields.Integer(compute='_compute_unit_stats', store=True)
    occupancy_rate = fields.Float('Physical Occupancy (%)', compute='_compute_unit_stats', store=True,
                                  aggregator='avg')
    lease_count = fields.Integer(compute='_compute_counts')
    work_order_count = fields.Integer(compute='_compute_counts')
    equipment_count = fields.Integer(compute='_compute_counts')
    exception_count = fields.Integer(compute='_compute_counts')
    tenant_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'The property code must be unique per company.'),
    ]

    @api.depends('ownership_ids.owner_id', 'ownership_ids.role', 'ownership_ids.date_from',
                 'ownership_ids.date_to', 'ownership_ids.percentage')
    def _compute_legal_owner(self):
        today = fields.Date.context_today(self)
        for rec in self:
            current = rec.ownership_ids.filtered(
                lambda o: o.role in ('legal_owner', 'co_owner')
                and (not o.date_from or o.date_from <= today) and (not o.date_to or o.date_to >= today))
            rec.legal_owner_id = current.sorted('percentage', reverse=True)[:1].owner_id

    @api.depends('valuation_ids.state', 'valuation_ids.value', 'valuation_ids.date')
    def _compute_valuation(self):
        for rec in self:
            approved = rec.valuation_ids.filtered(lambda v: v.state == 'approved').sorted(
                lambda v: (v.date, v.id), reverse=True)[:1]
            rec.current_valuation = approved.value if approved else rec.purchase_price
            rec.last_valuation_date = approved.date if approved else False

    @api.depends('title_issue_date', 'title_term_years')
    def _compute_title_expiry(self):
        for rec in self:
            if rec.title_issue_date and rec.title_term_years:
                rec.title_expiry_date = rec.title_issue_date + relativedelta(years=rec.title_term_years)
            elif not rec.title_expiry_date:
                rec.title_expiry_date = False

    @api.depends('unit_ids.area_sqm', 'unit_ids.is_lettable', 'unit_ids.occupancy_status', 'unit_ids.active',
                 'building_ids')
    def _compute_unit_stats(self):
        for rec in self:
            units = rec.unit_ids.filtered(lambda u: u.is_lettable and u.occupancy_status != 'unavailable')
            occupied = units.filtered(lambda u: u.occupancy_status == 'occupied')
            rec.building_count = len(rec.building_ids)
            rec.unit_count = len(units)
            rec.occupied_unit_count = len(occupied)
            rec.vacant_unit_count = len(units) - len(occupied)
            rec.occupancy_rate = (100.0 * len(occupied) / len(units)) if units else 0.0
            rec.lettable_area_sqm = sum(rec.unit_ids.filtered('is_lettable').mapped('area_sqm'))

    def _compute_counts(self):
        Lease = self.env['re.lease']
        WO = self.env['re.work.order']
        Equipment = self.env['maintenance.equipment']
        Exc = self.env['re.exception']
        for rec in self:
            rec.lease_count = Lease.search_count([('property_id', '=', rec.id)])
            rec.work_order_count = WO.search_count([('property_id', '=', rec.id)])
            rec.equipment_count = Equipment.search_count([('re_property_id', '=', rec.id)])
            rec.exception_count = Exc.search_count([('property_id', '=', rec.id), ('state', 'in', ('new', 'investigating'))])
            rec.tenant_count = len(Lease.search([('property_id', '=', rec.id),
                                                 ('state', 'in', ('active', 'expiring'))]).mapped('tenant_id'))

    @api.constrains('latitude', 'longitude')
    def _check_gps(self):
        for rec in self:
            if not (-90 <= rec.latitude <= 90) or not (-180 <= rec.longitude <= 180):
                raise ValidationError(_('Invalid GPS coordinates.'))

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._re_ensure_analytic_account()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'code' in vals:
            for rec in self.filtered('analytic_account_id'):
                rec.analytic_account_id.sudo().write({'name': rec.name, 'code': rec.code})
        return res

    def _re_ensure_analytic_account(self):
        plan = self.env.ref('real_estate_lifecycle.analytic_plan_property', raise_if_not_found=False)
        if not plan:
            return
        for rec in self.filtered(lambda r: not r.analytic_account_id):
            rec.analytic_account_id = self.env['account.analytic.account'].sudo().create({
                'name': rec.name,
                'code': rec.code,
                'plan_id': plan.id,
                'company_id': rec.company_id.id,
            })

    def _re_analytic_distribution(self, building=None):
        """Analytic distribution dict for invoices / bills of this property."""
        self.ensure_one()
        dist = {}
        if self.analytic_account_id:
            dist[str(self.analytic_account_id.id)] = 100.0
        if building and building.analytic_account_id:
            dist[str(building.analytic_account_id.id)] = 100.0
        return dist

    # ------------------------------------------------------------------
    def action_activate(self):
        self.write({'state': 'active'})

    def action_set_development(self):
        self.write({'state': 'under_development'})

    def action_dispose(self):
        for rec in self:
            if rec.lease_ids.filtered(lambda l: l.state in ('active', 'expiring', 'approved')):
                raise UserError(_('Property %s still has active leases.', rec.display_name))
        self.write({'state': 'disposed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def _action_open(self, xmlid, domain, context=None):
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = domain
        action['context'] = dict(context or {})
        return action

    def action_view_buildings(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_building', [('property_id', '=', self.id)],
                                 {'default_property_id': self.id})

    def action_view_units(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_unit', [('property_id', '=', self.id)],
                                 {'default_property_id': self.id})

    def action_view_leases(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_lease', [('property_id', '=', self.id)],
                                 {'default_property_id': self.id})

    def action_view_work_orders(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_work_order', [('property_id', '=', self.id)],
                                 {'default_property_id': self.id})

    def action_view_equipment(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_equipment', [('re_property_id', '=', self.id)],
                                 {'default_re_property_id': self.id})

    def action_view_exceptions(self):
        self.ensure_one()
        return self._action_open('real_estate_lifecycle.action_re_exception', [('property_id', '=', self.id)])

    def action_view_tenants(self):
        self.ensure_one()
        tenants = self.env['re.lease'].search([('property_id', '=', self.id),
                                               ('state', 'in', ('active', 'expiring'))]).mapped('tenant_id')
        return self._action_open('real_estate_lifecycle.action_re_tenant', [('id', 'in', tenants.ids)])

    def action_view_journal_items(self):
        """Property ledger: all posted journal items analytically allocated to this property."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Property Ledger: %s', self.display_name),
            'res_model': 'account.move.line',
            'view_mode': 'pivot,list,graph',
            'domain': [('re_property_id', '=', self.id), ('parent_state', '=', 'posted')],
            'context': {'pivot_row_groupby': ['account_id'], 'pivot_column_groupby': ['date:month'],
                        'pivot_measures': ['balance']},
        }

    def action_view_profitability(self):
        self.ensure_one()
        return self.env['re.report.wizard'].create({
            'report_type': 'property_income', 'property_ids': [(6, 0, self.ids)],
        }).action_print_pdf()


class RePropertyOwnership(models.Model):
    _name = 're.property.ownership'
    _description = 'Property Ownership'
    _inherit = ['mail.thread']
    _order = 'property_id, date_from desc'

    property_id = fields.Many2one('re.property', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True)
    owner_id = fields.Many2one('res.partner', 'Owner / Investor', required=True, tracking=True)
    role = fields.Selection([
        ('legal_owner', 'Legal Owner'),
        ('co_owner', 'Co-owner'),
        ('beneficial_owner', 'Beneficial Owner'),
        ('investor', 'Investor'),
    ], required=True, default='legal_owner', tracking=True)
    percentage = fields.Float('Ownership (%)', default=100.0, tracking=True)
    date_from = fields.Date('Effective From', required=True, default=fields.Date.context_today, tracking=True)
    date_to = fields.Date('Effective To', tracking=True)
    is_current = fields.Boolean(compute='_compute_is_current')
    reference = fields.Char('Transfer / Deed Reference')
    note = fields.Text()

    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_current = (not rec.date_from or rec.date_from <= today) and (not rec.date_to or rec.date_to >= today)

    @api.constrains('percentage', 'date_from', 'date_to', 'role')
    def _check_percentage(self):
        for rec in self:
            if rec.percentage <= 0 or rec.percentage > 100:
                raise ValidationError(_('Ownership percentage must be between 0 and 100.'))
            if rec.date_to and rec.date_from and rec.date_to < rec.date_from:
                raise ValidationError(_('Ownership end date must be after start date.'))
            legal_roles = ('legal_owner', 'co_owner')
            if rec.role not in legal_roles:
                continue
            overlapping = rec.property_id.ownership_ids.filtered(
                lambda o: o.role in legal_roles
                and (not o.date_to or not rec.date_from or o.date_to >= rec.date_from)
                and (not rec.date_to or not o.date_from or o.date_from <= rec.date_to))
            if sum(overlapping.mapped('percentage')) > 100.0001:
                raise ValidationError(_('Legal ownership of %s exceeds 100%% for overlapping periods.',
                                        rec.property_id.display_name))


class RePropertyValuation(models.Model):
    _name = 're.property.valuation'
    _description = 'Property Valuation'
    _inherit = ['mail.thread', 're.approval.mixin']
    _order = 'date desc, id desc'
    _re_approval_document_type = 'valuation'

    property_id = fields.Many2one('re.property', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True)
    currency_id = fields.Many2one(related='property_id.currency_id')
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    valuer_id = fields.Many2one('res.partner', 'Valuer', tracking=True)
    method = fields.Selection([
        ('market', 'Market Comparison'), ('income', 'Income Capitalisation'), ('dcf', 'Discounted Cash Flow'),
        ('cost', 'Depreciated Replacement Cost'), ('residual', 'Residual'), ('other', 'Other')],
        required=True, default='market')
    purpose = fields.Selection([
        ('financial_reporting', 'Financial Reporting'), ('lending', 'Bank / Lending'),
        ('insurance', 'Insurance'), ('acquisition', 'Acquisition / Disposal'), ('internal', 'Internal')],
        default='financial_reporting')
    value = fields.Monetary(required=True, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('to_approve', 'Pending Approval'), ('approved', 'Approved'),
                              ('rejected', 'Rejected')], default='draft', tracking=True)
    note = fields.Text()

    def _re_approval_amount(self):
        return self.value

    def action_submit(self):
        for rec in self:
            if rec._re_request_approval():
                rec.state = 'approved'
            else:
                rec.state = 'to_approve'

    def action_approve(self):
        self._re_approve()
        self.write({'state': 'approved'})

    def _re_after_reject(self):
        self.write({'state': 'rejected'})

    def write(self, vals):
        if any(rec.state == 'approved' for rec in self) and set(vals) & {'value', 'date', 'property_id'}:
            raise UserError(_('Approved valuations are part of the valuation history and cannot be changed. '
                              'Record a new valuation instead.'))
        return super().write(vals)


class ReLandEncumbrance(models.Model):
    _name = 're.land.encumbrance'
    _description = 'Land Encumbrance'
    _inherit = ['mail.thread']
    _order = 'registration_date desc'

    property_id = fields.Many2one('re.property', required=True, ondelete='cascade', index=True)
    unit_id = fields.Many2one('re.unit', 'Plot', domain="[('property_id', '=', property_id)]")
    company_id = fields.Many2one(related='property_id.company_id', store=True)
    currency_id = fields.Many2one(related='property_id.currency_id')
    encumbrance_type = fields.Selection([
        ('mortgage', 'Mortgage / Charge'), ('caveat', 'Caveat'), ('easement', 'Easement / Way-leave'),
        ('dispute', 'Ownership Dispute'), ('lease', 'Registered Lease'), ('other', 'Other')], required=True)
    holder_id = fields.Many2one('res.partner', 'Holder / Beneficiary')
    amount = fields.Monetary()
    reference = fields.Char('Registration Reference')
    registration_date = fields.Date()
    state = fields.Selection([('active', 'Active'), ('released', 'Released')], default='active', tracking=True)
    release_date = fields.Date()
    note = fields.Text()
