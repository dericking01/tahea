# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ReMaintenancePlan(models.Model):
    """Recurring preventive maintenance. Time-based plans generate work orders
    ``lead_days`` before the due date. Usage-based plans generate a work order when
    the linked run-hour meter passes the next usage threshold (only when real meter
    readings are recorded - nothing is extrapolated)."""
    _name = 're.maintenance.plan'
    _description = 'Preventive Maintenance Plan'
    _inherit = ['mail.thread']
    _order = 'next_date'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    equipment_id = fields.Many2one('maintenance.equipment', index=True)
    property_id = fields.Many2one('re.property', required=True, index=True)
    building_id = fields.Many2one('re.building', domain="[('property_id', '=', property_id)]")
    company_id = fields.Many2one(related='property_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    category_id = fields.Many2one('re.maintenance.category')
    trigger = fields.Selection([('time', 'Calendar Interval'), ('usage', 'Usage (meter readings)')],
                               default='time', required=True)
    interval_number = fields.Integer(default=3)
    interval_type = fields.Selection([('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')],
                                     default='months')
    next_date = fields.Date(default=fields.Date.context_today)
    lead_days = fields.Integer('Create Work Order (days before)', default=7)
    usage_meter_id = fields.Many2one('re.meter', 'Run-hour Meter',
                                     domain="[('utility_type', '=', 'equipment_hours')]")
    usage_interval = fields.Float('Usage Interval (hours)')
    next_usage = fields.Float('Next Service at (hours)')
    technician_id = fields.Many2one('res.users')
    contractor_id = fields.Many2one('res.partner', domain="[('re_is_contractor', '=', True)]")
    estimated_cost = fields.Monetary()
    instructions = fields.Html('Checklist / Instructions')
    work_order_ids = fields.One2many('re.work.order', 'plan_id')
    work_order_count = fields.Integer(compute='_compute_compliance')
    compliance_rate = fields.Float('On-time Compliance (%)', compute='_compute_compliance')

    @api.constrains('interval_number', 'trigger', 'usage_interval')
    def _check_interval(self):
        for rec in self:
            if rec.trigger == 'time' and rec.interval_number <= 0:
                raise ValidationError(_('The interval must be positive.'))
            if rec.trigger == 'usage' and (rec.usage_interval <= 0 or not rec.usage_meter_id):
                raise ValidationError(_('Usage plans need a run-hour meter and a positive usage interval.'))

    def _compute_compliance(self):
        for rec in self:
            done = rec.work_order_ids.filtered(lambda w: w.date_done)
            rec.work_order_count = len(rec.work_order_ids)
            on_time = done.filtered(lambda w: w.scheduled_date and w.date_done <= w.scheduled_date)
            rec.compliance_rate = 100.0 * len(on_time) / len(done) if done else 0.0

    def _next(self, d):
        return d + relativedelta(**{self.interval_type: self.interval_number})

    def _wo_vals(self, scheduled):
        self.ensure_one()
        return {
            'title': self.name, 'property_id': self.property_id.id, 'building_id': self.building_id.id,
            'equipment_id': self.equipment_id.id, 'maintenance_type': 'preventive',
            'category_id': self.category_id.id, 'technician_id': self.technician_id.id,
            'contractor_id': self.contractor_id.id,
            'execution': 'contractor' if self.contractor_id else 'internal',
            'estimated_cost': self.estimated_cost, 'description': self.instructions, 'plan_id': self.id,
            'scheduled_date': scheduled, 'date_target': scheduled, 'state': 'triage',
        }

    def _generate(self, today=None):
        today = today or fields.Date.context_today(self)
        WO = self.env['re.work.order']
        created = WO
        for plan in self.filtered('active'):
            if plan.trigger == 'time':
                while plan.next_date and plan.next_date - timedelta(days=plan.lead_days) <= today:
                    if not WO.search_count([('plan_id', '=', plan.id), ('scheduled_date', '=', plan.next_date)]):
                        created |= WO.create(plan._wo_vals(plan.next_date))
                    plan.next_date = plan._next(plan.next_date)
            elif plan.usage_meter_id and plan.next_usage:
                last = plan.usage_meter_id.last_reading
                if last >= plan.next_usage:
                    created |= WO.create(plan._wo_vals(today))
                    plan.next_usage = plan.next_usage + plan.usage_interval
        return created

    def action_generate_now(self):
        wos = self._generate()
        return {'type': 'ir.actions.act_window', 'res_model': 're.work.order', 'view_mode': 'list,form',
                'domain': [('id', 'in', wos.ids)], 'name': _('Generated Work Orders')}

    @api.model
    def _cron_generate(self):
        self.search([])._generate()
        # reminders for preventive work orders about to become overdue
        today = fields.Date.context_today(self)
        soon = self.env['re.work.order'].search([('maintenance_type', '=', 'preventive'),
                                                 ('state', 'not in', ('completed', 'tenant_confirmation', 'closed',
                                                                      'cancelled')),
                                                 ('date_target', '<=', today + timedelta(days=2))])
        for wo in soon:
            user = wo.technician_id or wo.manager_id
            if user and not wo.activity_ids.filtered(lambda a: a.user_id == user):
                wo.activity_schedule('mail.mail_activity_data_todo', user_id=user.id, date_deadline=wo.date_target,
                                     summary=_('Preventive maintenance due'))
