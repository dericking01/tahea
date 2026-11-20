# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ReBuilding(models.Model):
    _name = 're.building'
    _description = 'Building'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'property_id, code, name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    property_id = fields.Many2one('re.property', required=True, ondelete='restrict', index=True, tracking=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    manager_id = fields.Many2one(related='property_id.manager_id', store=True)
    portfolio_id = fields.Many2one(related='property_id.portfolio_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    building_use = fields.Selection([
        ('residential', 'Residential'), ('office', 'Office'), ('retail', 'Retail'), ('industrial', 'Industrial'),
        ('warehouse', 'Warehouse'), ('hotel', 'Hotel / Serviced'), ('mixed', 'Mixed-use'), ('other', 'Other')],
        default='mixed')
    year_built = fields.Integer()
    commissioning_date = fields.Date()
    gross_area = fields.Float('Gross Area (m²)')
    condition = fields.Selection([
        ('new', 'New'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor')], default='good', tracking=True)
    floor_ids = fields.One2many('re.floor', 'building_id')
    unit_ids = fields.One2many('re.unit', 'building_id')
    floor_count = fields.Integer(compute='_compute_stats', store=True)
    unit_count = fields.Integer('Lettable Units', compute='_compute_stats', store=True)
    occupied_unit_count = fields.Integer(compute='_compute_stats', store=True)
    lettable_area_sqm = fields.Float('Lettable Area (m²)', compute='_compute_stats', store=True)
    occupancy_rate = fields.Float('Physical Occupancy (%)', compute='_compute_stats', store=True, aggregator='avg')
    analytic_account_id = fields.Many2one('account.analytic.account', copy=False, readonly=True, index=True)
    equipment_count = fields.Integer(compute='_compute_counts')
    work_order_count = fields.Integer(compute='_compute_counts')
    issue_count = fields.Integer(compute='_compute_counts')
    note = fields.Html()

    @api.depends('floor_ids', 'unit_ids.area_sqm', 'unit_ids.is_lettable', 'unit_ids.occupancy_status',
                 'unit_ids.active')
    def _compute_stats(self):
        for rec in self:
            units = rec.unit_ids.filtered(lambda u: u.is_lettable and u.occupancy_status != 'unavailable')
            occupied = units.filtered(lambda u: u.occupancy_status == 'occupied')
            rec.floor_count = len(rec.floor_ids)
            rec.unit_count = len(units)
            rec.occupied_unit_count = len(occupied)
            rec.lettable_area_sqm = sum(rec.unit_ids.filtered('is_lettable').mapped('area_sqm'))
            rec.occupancy_rate = 100.0 * len(occupied) / len(units) if units else 0.0

    def _compute_counts(self):
        for rec in self:
            rec.equipment_count = self.env['maintenance.equipment'].search_count([('re_building_id', '=', rec.id)])
            rec.work_order_count = self.env['re.work.order'].search_count([('building_id', '=', rec.id)])
            rec.issue_count = self.env['re.building.issue'].search_count([('building_id', '=', rec.id),
                                                                          ('state', '=', 'open')])

    @api.constrains('property_id')
    def _check_not_land(self):
        for rec in self:
            if rec.property_id.is_land:
                raise ValidationError(_('Land properties are managed as plots and cannot contain buildings. '
                                        'Change the property type first if the land has been developed.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        plan = self.env.ref('real_estate_lifecycle.analytic_plan_building', raise_if_not_found=False)
        if plan:
            for rec in records:
                rec.analytic_account_id = self.env['account.analytic.account'].sudo().create({
                    'name': '%s / %s' % (rec.property_id.name, rec.name),
                    'code': rec.code,
                    'plan_id': plan.id,
                    'company_id': rec.company_id.id,
                })
        return records

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s' % (rec.property_id.code, rec.name) if rec.property_id else rec.name

    def action_view_units(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_unit')
        action['domain'] = [('building_id', '=', self.id)]
        action['context'] = {'default_building_id': self.id, 'default_property_id': self.property_id.id}
        return action

    def action_view_floors(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_floor')
        action['domain'] = [('building_id', '=', self.id)]
        action['context'] = {'default_building_id': self.id}
        return action

    def action_view_equipment(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_equipment')
        action['domain'] = [('re_building_id', '=', self.id)]
        action['context'] = {'default_re_building_id': self.id, 'default_re_property_id': self.property_id.id}
        return action

    def action_view_work_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_work_order')
        action['domain'] = [('building_id', '=', self.id)]
        action['context'] = {'default_building_id': self.id, 'default_property_id': self.property_id.id}
        return action

    def action_view_issues(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_building_issue')
        action['domain'] = [('building_id', '=', self.id)]
        return action


class ReFloor(models.Model):
    _name = 're.floor'
    _description = 'Floor'
    _order = 'building_id, level, id'

    name = fields.Char(required=True)
    level = fields.Integer('Level', help='0 = ground floor, negative = basement')
    building_id = fields.Many2one('re.building', required=True, ondelete='cascade', index=True)
    property_id = fields.Many2one(related='building_id.property_id', store=True)
    company_id = fields.Many2one(related='building_id.company_id', store=True)
    area = fields.Float('Floor Area (m²)')
    unit_ids = fields.One2many('re.unit', 'floor_id')
    unit_count = fields.Integer(compute='_compute_unit_count')

    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s' % (rec.building_id.name, rec.name) if rec.building_id else rec.name
