# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _


class MaintenanceEquipment(models.Model):
    """Building equipment register. Physical equipment is distinct from the
    capitalised fixed asset (account.asset) but can be linked to it."""
    _inherit = 'maintenance.equipment'

    re_asset_code = fields.Char('Asset ID', copy=False, index=True)
    re_property_id = fields.Many2one('re.property', 'Property', index=True, tracking=True)
    re_building_id = fields.Many2one('re.building', 'Building', domain="[('property_id', '=', re_property_id)]")
    re_floor_id = fields.Many2one('re.floor', 'Floor', domain="[('building_id', '=', re_building_id)]")
    re_unit_id = fields.Many2one('re.unit', 'Unit / Space', domain="[('property_id', '=', re_property_id)]")
    re_asset_category_id = fields.Many2one('re.asset.category', 'Building System Category')
    re_manufacturer = fields.Char('Manufacturer')
    re_installation_date = fields.Date('Installation / Commissioning Date')
    re_criticality = fields.Selection([('low', 'Low'), ('medium', 'Medium'), ('high', 'High'),
                                       ('critical', 'Critical')], 'Criticality', default='medium', tracking=True)
    re_condition = fields.Selection([('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'),
                                     ('poor', 'Poor'), ('failed', 'Failed')], 'Condition', default='good',
                                    tracking=True)
    re_service_contract_id = fields.Many2one('re.vendor.contract', 'Service Agreement')
    re_replacement_cost = fields.Monetary('Estimated Replacement Cost', currency_field='re_currency_id')
    re_expected_life_years = fields.Float('Expected Useful Life (years)')
    re_downtime_impact = fields.Selection([('none', 'No tenant impact'), ('minor', 'Minor'), ('major', 'Major'),
                                           ('critical', 'Building critical')], 'Downtime Impact', default='minor')
    re_currency_id = fields.Many2one('res.currency', compute='_compute_re_currency')
    account_asset_id = fields.Many2one('account.asset', 'Fixed Asset (Accounting)',
                                       help='Link to the capitalised asset in Accounting, if any.')
    re_work_order_ids = fields.One2many('re.work.order', 'equipment_id', 'Work Orders')
    re_work_order_count = fields.Integer(compute='_compute_re_costs')
    re_maintenance_cost_total = fields.Monetary('Cumulative Maintenance Cost', compute='_compute_re_costs',
                                                currency_field='re_currency_id')
    re_cost_12m = fields.Monetary('Maintenance Cost (12 months)', compute='_compute_re_costs',
                                  currency_field='re_currency_id')
    re_failures_12m = fields.Integer('Corrective / Emergency Jobs (12 months)', compute='_compute_re_costs')
    re_downtime_hours = fields.Float('Downtime Hours (total)', compute='_compute_re_costs')
    re_age_years = fields.Float('Age (years)', compute='_compute_re_costs')
    re_remaining_life_years = fields.Float('Remaining Useful Life (years)', compute='_compute_re_costs')
    re_expected_future_repair = fields.Monetary('Expected Repair Cost (remaining life)', compute='_compute_re_costs',
                                                currency_field='re_currency_id')
    re_recommendation = fields.Selection([
        ('repair', 'Continue Maintenance'), ('inspect', 'Inspect / Condition Survey'),
        ('replace', 'Review for Replacement')], 'Recommendation', compute='_compute_re_costs')
    re_recommendation_reason = fields.Text('Recommendation Basis', compute='_compute_re_costs')

    def _compute_re_currency(self):
        for rec in self:
            rec.re_currency_id = (rec.company_id or self.env.company).currency_id

    @api.onchange('re_asset_category_id')
    def _onchange_re_asset_category(self):
        if self.re_asset_category_id:
            self.re_expected_life_years = self.re_asset_category_id.expected_life_years
            self.re_criticality = self.re_asset_category_id.default_criticality

    @api.onchange('re_building_id')
    def _onchange_re_building(self):
        if self.re_building_id:
            self.re_property_id = self.re_building_id.property_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('re_asset_code') and (vals.get('re_property_id') or vals.get('re_building_id')):
                vals['re_asset_code'] = self.env['ir.sequence'].next_by_code('re.equipment')
        return super().create(vals_list)

    def _compute_re_costs(self):
        today = fields.Date.context_today(self)
        year_ago = today - timedelta(days=365)
        for rec in self:
            wos = rec.re_work_order_ids.filtered(lambda w: w.state != 'cancelled')
            rec.re_work_order_count = len(wos)
            total = sum(wos.mapped('actual_cost'))
            recent = wos.filtered(lambda w: (w.date_done or w.date_request or today) >= year_ago)
            cost_12m = sum(recent.mapped('actual_cost'))
            failures = recent.filtered(lambda w: w.maintenance_type in ('corrective', 'emergency'))
            rec.re_maintenance_cost_total = total
            rec.re_cost_12m = cost_12m
            rec.re_failures_12m = len(failures)
            rec.re_downtime_hours = sum(wos.mapped('downtime_hours'))
            start = rec.re_installation_date or rec.effective_date
            age = (today - start).days / 365.25 if start else 0.0
            rec.re_age_years = age
            life = rec.re_expected_life_years or rec.re_asset_category_id.expected_life_years or 0.0
            remaining = max(0.0, life - age) if life else 0.0
            rec.re_remaining_life_years = remaining
            # Expected future repair = recent annual run-rate x remaining life (simple, documented estimate)
            rec.re_expected_future_repair = cost_12m * remaining
            threshold = (rec.re_asset_category_id.replacement_threshold_pct or 60.0) / 100.0
            reasons = []
            recommendation = 'repair'
            replacement = rec.re_replacement_cost
            if replacement and total >= threshold * replacement:
                recommendation = 'replace'
                reasons.append(_('Cumulative repair cost %(c)s is %(p).0f%% of the replacement cost %(r)s '
                                 '(review threshold %(t).0f%%).', c=rec.re_currency_id.format(total),
                                 p=100 * total / replacement, r=rec.re_currency_id.format(replacement),
                                 t=threshold * 100))
            if replacement and (total + rec.re_expected_future_repair) > replacement and remaining:
                recommendation = 'replace'
                reasons.append(_('Past plus expected future repairs exceed the replacement cost.'))
            if life and age >= life:
                recommendation = 'replace' if rec.re_criticality in ('high', 'critical') else (
                    'inspect' if recommendation == 'repair' else recommendation)
                reasons.append(_('The asset has reached its expected useful life (%(a).1f of %(l).1f years).',
                                 a=age, l=life))
            if len(failures) >= 3 and recommendation == 'repair':
                recommendation = 'inspect'
                reasons.append(_('%s corrective/emergency jobs in the last 12 months.', len(failures)))
            if rec.re_condition in ('poor', 'failed') and recommendation == 'repair':
                recommendation = 'inspect'
                reasons.append(_('Condition recorded as %s.', dict(self._fields['re_condition'].selection)[rec.re_condition]))
            if not reasons:
                reasons.append(_('Costs and failures are within normal limits.'))
            if not replacement:
                reasons.append(_('No replacement cost estimate recorded; the analysis is incomplete.'))
            reasons.append(_('This is a decision-support recommendation only; replacement requires a management '
                             'decision and capital approval.'))
            rec.re_recommendation = recommendation
            rec.re_recommendation_reason = '\n'.join(reasons)

    def action_view_re_work_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_work_order')
        action['domain'] = [('equipment_id', '=', self.id)]
        action['context'] = {'default_equipment_id': self.id, 'default_property_id': self.re_property_id.id,
                             'default_building_id': self.re_building_id.id}
        return action
