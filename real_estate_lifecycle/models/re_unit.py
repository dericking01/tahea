# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

UNIT_TYPES = [
    ('apartment', 'Apartment'),
    ('studio', 'Studio'),
    ('house', 'House / Villa'),
    ('office', 'Office'),
    ('retail', 'Retail Shop'),
    ('kiosk', 'Kiosk'),
    ('warehouse', 'Warehouse'),
    ('industrial', 'Industrial Unit'),
    ('hotel_room', 'Hotel / Serviced Room'),
    ('parking', 'Parking Bay'),
    ('storage', 'Storage'),
    ('plot', 'Land Plot'),
    ('common', 'Common Area'),
    ('other', 'Other'),
]

LIVE_LEASE_STATES = ('active', 'expiring')
RESERVED_LEASE_STATES = ('to_approve', 'approved')


class ReUnit(models.Model):
    _name = 're.unit'
    _description = 'Rental Unit / Space / Plot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'property_id, building_id, floor_id, name'

    name = fields.Char('Unit / Plot Number', required=True, tracking=True)
    active = fields.Boolean(default=True)
    property_id = fields.Many2one('re.property', required=True, ondelete='restrict', index=True, tracking=True)
    building_id = fields.Many2one('re.building', ondelete='restrict', index=True,
                                  domain="[('property_id', '=', property_id)]")
    floor_id = fields.Many2one('re.floor', ondelete='restrict', domain="[('building_id', '=', building_id)]")
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    manager_id = fields.Many2one(related='property_id.manager_id', store=True)
    portfolio_id = fields.Many2one(related='property_id.portfolio_id', store=True)
    property_type_id = fields.Many2one(related='property_id.property_type_id', store=True)
    region = fields.Char(related='property_id.region', store=True)
    unit_type = fields.Selection(UNIT_TYPES, required=True, default='apartment')
    is_plot = fields.Boolean(compute='_compute_is_plot', store=True)

    # Physical (never mixed with occupancy / rental status)
    area = fields.Float('Area', tracking=True)
    area_unit_id = fields.Many2one('re.area.unit', default=lambda self: self.env['re.area.unit']._default_unit())
    area_sqm = fields.Float('Area (m²)', compute='_compute_area_sqm', store=True, aggregator='sum')
    bedrooms = fields.Integer()
    bathrooms = fields.Integer()
    furnished = fields.Boolean()

    is_lettable = fields.Boolean(
        'Rentable', default=True,
        help='Uncheck for common areas, management offices or spaces never offered for rent. '
             'Non-rentable units are excluded from occupancy KPIs.')
    allow_multi_occupancy = fields.Boolean(
        'Allow Multiple Concurrent Leases', groups='real_estate_lifecycle.group_re_portfolio_manager',
        help='Authorised configuration for shared spaces (co-working desks, shared kiosks).')

    # Occupancy (physical) - maintained by lease activation / move-out, editable by staff
    occupancy_status = fields.Selection([
        ('vacant', 'Vacant'),
        ('occupied', 'Occupied'),
        ('owner_occupied', 'Owner Occupied'),
        ('unavailable', 'Unavailable (refurbishment / withdrawn)'),
    ], default='vacant', required=True, tracking=True)
    vacant_since = fields.Date(tracking=True)
    # Rental (contractual) - derived from leases
    rental_status = fields.Selection([
        ('available', 'Available'),
        ('reserved', 'Reserved (lease pending)'),
        ('let', 'Let'),
        ('not_lettable', 'Not Rentable'),
    ], compute='_compute_rental_status', store=True)
    lease_ids = fields.Many2many('re.lease', 're_lease_unit_rel', 'unit_id', 'lease_id', string='Leases')
    active_lease_id = fields.Many2one('re.lease', compute='_compute_rental_status', store=True)
    tenant_id = fields.Many2one('res.partner', compute='_compute_rental_status', store=True)
    lease_end_date = fields.Date(compute='_compute_rental_status', store=True)

    market_rent = fields.Monetary('Expected Monthly Rent',
                                  help='Expected (market) monthly rental value; used for gross potential rent.')
    current_rent = fields.Monetary('Current Monthly Rent', compute='_compute_current_rent')
    service_charge_basis = fields.Selection([
        ('area', 'By Area'), ('equal', 'Equal Share'), ('custom', 'Custom Percentage'), ('excluded', 'Excluded')],
        default='area', string='Service-Charge Basis')
    service_charge_share = fields.Float('Custom Service-Charge Share (%)')

    meter_ids = fields.One2many('re.meter', 'unit_id')
    electricity_meter_id = fields.Many2one('re.meter', compute='_compute_meters')
    water_meter_id = fields.Many2one('re.meter', compute='_compute_meters')

    # Plot specific
    survey_number = fields.Char('Survey No.')
    land_use = fields.Selection([
        ('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'),
        ('agricultural', 'Agricultural'), ('mixed', 'Mixed'), ('institutional', 'Institutional')])
    plot_status = fields.Selection([
        ('available', 'Available'), ('reserved', 'Reserved'), ('allocated', 'Allocated'),
        ('sold', 'Sold'), ('leased', 'Leased')], default='available', tracking=True)
    plot_title_number = fields.Char('Plot Title No.')
    plot_value = fields.Monetary('Plot Valuation')
    buyer_id = fields.Many2one('res.partner', 'Allocated To / Buyer')

    work_order_ids = fields.One2many('re.work.order', 'unit_id')
    work_order_count = fields.Integer(compute='_compute_counts')
    lease_count = fields.Integer(compute='_compute_counts')
    vacancy_days = fields.Integer(compute='_compute_vacancy_days')
    note = fields.Text()

    _sql_constraints = [
        ('name_property_uniq', 'unique(name, property_id, building_id)',
         'Unit number must be unique within a building/property.'),
    ]

    @api.depends('unit_type')
    def _compute_is_plot(self):
        for rec in self:
            rec.is_plot = rec.unit_type == 'plot'

    @api.depends('area', 'area_unit_id.factor_to_sqm')
    def _compute_area_sqm(self):
        for rec in self:
            rec.area_sqm = rec.area_unit_id._to_sqm(rec.area) if rec.area_unit_id else rec.area

    @api.depends('lease_ids.state', 'lease_ids.tenant_id', 'lease_ids.date_end', 'is_lettable')
    def _compute_rental_status(self):
        for rec in self:
            live = rec.lease_ids.filtered(lambda l: l.state in LIVE_LEASE_STATES).sorted('date_start', reverse=True)
            reserved = rec.lease_ids.filtered(lambda l: l.state in RESERVED_LEASE_STATES)
            if not rec.is_lettable:
                status = 'not_lettable'
            elif live:
                status = 'let'
            elif reserved:
                status = 'reserved'
            else:
                status = 'available'
            rec.rental_status = status
            rec.active_lease_id = live[:1]
            rec.tenant_id = live[:1].tenant_id
            rec.lease_end_date = live[:1].effective_end_date

    def _compute_current_rent(self):
        for rec in self:
            lease = rec.active_lease_id
            if not lease:
                rec.current_rent = 0.0
                continue
            today = fields.Date.context_today(self)
            rent = lease._get_rent_rate(today)
            total_area = sum(lease.unit_ids.mapped('area_sqm'))
            share = (rec.area_sqm / total_area) if total_area else 1.0 / max(len(lease.unit_ids), 1)
            rec.current_rent = rent * share

    def _compute_meters(self):
        for rec in self:
            rec.electricity_meter_id = rec.meter_ids.filtered(lambda m: m.utility_type == 'electricity')[:1]
            rec.water_meter_id = rec.meter_ids.filtered(lambda m: m.utility_type == 'water')[:1]

    def _compute_counts(self):
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)
            rec.lease_count = len(rec.lease_ids)

    def _compute_vacancy_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.vacancy_days = (today - rec.vacant_since).days if (
                rec.occupancy_status == 'vacant' and rec.vacant_since) else 0

    @api.onchange('building_id')
    def _onchange_building(self):
        if self.building_id:
            self.property_id = self.building_id.property_id

    @api.constrains('building_id', 'floor_id', 'property_id', 'unit_type')
    def _check_hierarchy(self):
        for rec in self:
            if rec.building_id and rec.building_id.property_id != rec.property_id:
                raise ValidationError(_('Unit %s: the building does not belong to the selected property.', rec.name))
            if rec.floor_id and rec.floor_id.building_id != rec.building_id:
                raise ValidationError(_('Unit %s: the floor does not belong to the selected building.', rec.name))
            if rec.property_id.is_land and rec.unit_type != 'plot':
                raise ValidationError(_('Land properties can only contain plots.'))

    @api.constrains('service_charge_share')
    def _check_share(self):
        for rec in self:
            if rec.service_charge_share < 0 or rec.service_charge_share > 100:
                raise ValidationError(_('Service-charge share must be between 0 and 100%.'))

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if vals.get('occupancy_status', 'vacant') == 'vacant' and not vals.get('vacant_since'):
                vals['vacant_since'] = today
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('occupancy_status') == 'vacant' and 'vacant_since' not in vals:
            to_stamp = self.filtered(lambda u: u.occupancy_status != 'vacant')
            res = super().write(vals)
            to_stamp.write({'vacant_since': fields.Date.context_today(self)})
            return res
        if vals.get('occupancy_status') in ('occupied', 'owner_occupied') and 'vacant_since' not in vals:
            vals['vacant_since'] = False
        return super().write(vals)

    def _compute_display_name(self):
        for rec in self:
            parts = [rec.property_id.code or '']
            if rec.building_id:
                parts.append(rec.building_id.code or rec.building_id.name)
            parts.append(rec.name)
            rec.display_name = ' / '.join(p for p in parts if p)

    def action_view_leases(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_lease')
        action['domain'] = [('unit_ids', 'in', self.id)]
        action['context'] = {'default_property_id': self.property_id.id, 'default_unit_ids': [(6, 0, self.ids)],
                             'default_building_id': self.building_id.id}
        return action

    def action_view_work_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_work_order')
        action['domain'] = [('unit_id', '=', self.id)]
        action['context'] = {'default_unit_id': self.id, 'default_property_id': self.property_id.id,
                             'default_building_id': self.building_id.id}
        return action
