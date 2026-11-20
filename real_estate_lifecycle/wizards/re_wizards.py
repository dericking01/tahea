# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReRejectWizard(models.TransientModel):
    _name = 're.reject.wizard'
    _description = 'Reject Approval Request'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    reason = fields.Text(required=True)

    def action_reject(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        record._re_reject(self.reason)
        record._re_after_reject()
        return {'type': 'ir.actions.act_window_close'}


class ReLeaseTerminateWizard(models.TransientModel):
    _name = 're.lease.terminate.wizard'
    _description = 'Terminate Lease'

    lease_id = fields.Many2one('re.lease', required=True)
    termination_date = fields.Date(required=True, default=fields.Date.context_today)
    termination_type = fields.Selection([
        ('early_tenant', 'Early - Tenant Request'), ('early_landlord', 'Early - Landlord (default / breach)'),
        ('mutual', 'Mutual Agreement'), ('break_clause', 'Break Clause Exercised'), ('natural', 'End of Term')],
        required=True, default='early_tenant')
    reason = fields.Text(required=True)
    vacate_units = fields.Boolean('Tenant has moved out', default=True)
    notice_warning = fields.Char(compute='_compute_notice_warning')

    @api.depends('lease_id', 'termination_date')
    def _compute_notice_warning(self):
        today = fields.Date.context_today(self)
        for rec in self:
            notice = rec.lease_id.notice_period_days
            if rec.termination_date and notice and (rec.termination_date - today).days < notice:
                rec.notice_warning = _('Termination gives less than the contractual notice of %s days.', notice)
            else:
                rec.notice_warning = False

    def action_terminate(self):
        self.ensure_one()
        self.lease_id._re_terminate(self.termination_date, self.termination_type, self.reason, self.vacate_units)
        return {'type': 'ir.actions.act_window_close'}


class ReLeaseRenewWizard(models.TransientModel):
    _name = 're.lease.renew.wizard'
    _description = 'Renew Lease'

    lease_id = fields.Many2one('re.lease', required=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    date_start = fields.Date(required=True, compute='_compute_defaults', store=True, readonly=False, precompute=True)
    date_end = fields.Date(required=True, compute='_compute_defaults', store=True, readonly=False, precompute=True)
    rent_amount = fields.Monetary('New Monthly Rent', compute='_compute_defaults', store=True, readonly=False, precompute=True)
    copy_charges = fields.Boolean(default=True)

    @api.depends('lease_id')
    def _compute_defaults(self):
        for rec in self:
            lease = rec.lease_id
            start = lease.date_end + timedelta(days=1) if lease.date_end else fields.Date.context_today(self)
            rec.date_start = start
            rec.date_end = start + relativedelta(months=lease.duration_months or 12, days=-1)
            rec.rent_amount = lease._get_rent_rate(lease.date_end) if lease.date_end else lease.rent_amount

    def action_renew(self):
        self.ensure_one()
        lease = self.lease_id
        if lease.state not in ('active', 'expiring', 'expired'):
            raise UserError(_('Only active, expiring or expired leases can be renewed.'))
        if self.date_start <= lease.effective_end_date:
            raise UserError(_('The renewal must start after the current lease ends (%s).', lease.effective_end_date))
        new = lease.copy({
            'date_start': self.date_start, 'date_end': self.date_end, 'rent_amount': self.rent_amount,
            'parent_lease_id': lease.id, 'escalation_ids': [], 'state': 'draft',
            'rent_free_date_from': False, 'rent_free_date_to': False,
            'charge_ids': [(0, 0, {'charge_type': c.charge_type, 'name': c.name, 'amount': c.amount})
                           for c in lease.charge_ids if self.copy_charges and c.active
                           and c.charge_type not in ('concession',) and not c.service_charge_budget_id],
        })
        lease.message_post(body=_('Renewal %s prepared.', new.name))
        return {'type': 'ir.actions.act_window', 'res_model': 're.lease', 'res_id': new.id, 'view_mode': 'form'}


class ReRfqWizard(models.TransientModel):
    _name = 're.rfq.wizard'
    _description = 'Request Quotations for Work Order'

    work_order_id = fields.Many2one('re.work.order', required=True)
    vendor_ids = fields.Many2many('res.partner', string='Contractors', required=True,
                                  domain="[('re_is_contractor', '=', True)]")
    description = fields.Text(required=True, compute='_compute_description', store=True, readonly=False, precompute=True)
    quantity = fields.Float(default=1.0)

    @api.depends('work_order_id')
    def _compute_description(self):
        for rec in self:
            rec.description = '%s - %s' % (rec.work_order_id.name, rec.work_order_id.title) if rec.work_order_id else ''

    def action_create_rfqs(self):
        self.ensure_one()
        wo = self.work_order_id
        product = wo._re_product()
        dist = wo.property_id._re_analytic_distribution(wo.building_id)
        pos = self.env['purchase.order']
        for vendor in self.vendor_ids:
            non_compliant = '' if vendor.re_is_compliant else _(' (WARNING: %s)', vendor.re_compliance_note)
            po = self.env['purchase.order'].with_company(wo.company_id).create({
                'partner_id': vendor.id, 're_work_order_id': wo.id, 'origin': wo.name,
                'order_line': [(0, 0, {'product_id': product.id, 'name': self.description, 'product_qty': self.quantity,
                                       'price_unit': 0.0, 'analytic_distribution': dist,
                                       'date_planned': fields.Datetime.now()})],
            })
            po.message_post(body=_('RFQ for work order %s%s', wo.name, non_compliant))
            pos |= po
        if wo.state == 'new':
            wo.state = 'triage'
        wo.message_post(body=_('Quotations requested from: %s', ', '.join(self.vendor_ids.mapped('name'))))
        return wo.action_view_purchase_orders()


class ReBillingRunWizard(models.TransientModel):
    _name = 're.billing.run.wizard'
    _description = 'Run Rental Billing'

    date_to = fields.Date('Bill obligations up to', required=True, default=fields.Date.context_today)
    lease_ids = fields.Many2many('re.lease', string='Only these leases',
                                 domain="[('state', 'in', ('active', 'expiring', 'terminated', 'expired', 'renewed'))]")

    def action_run(self):
        run = self.env['re.billing.schedule']._cron_generate_rental_invoices(self.date_to, self.lease_ids.ids or None)
        return {'type': 'ir.actions.act_window', 'res_model': 're.billing.run', 'res_id': run.id, 'view_mode': 'form'}


class ReLandSubdivideWizard(models.TransientModel):
    _name = 're.land.subdivide.wizard'
    _description = 'Subdivide Land into Plots'

    property_id = fields.Many2one('re.property', required=True, domain="[('is_land', '=', True)]")
    prefix = fields.Char(required=True, default='PLOT-')
    start_number = fields.Integer(default=1)
    count = fields.Integer('Number of Plots', required=True, default=10)
    area = fields.Float('Area per Plot', required=True)
    area_unit_id = fields.Many2one('re.area.unit', required=True,
                                   default=lambda self: self.env['re.area.unit']._default_unit())
    land_use = fields.Selection([('residential', 'Residential'), ('commercial', 'Commercial'),
                                 ('industrial', 'Industrial'), ('agricultural', 'Agricultural'), ('mixed', 'Mixed'),
                                 ('institutional', 'Institutional')], default='residential')
    plot_value = fields.Float('Value per Plot')

    def action_subdivide(self):
        self.ensure_one()
        if self.count <= 0 or self.count > 2000:
            raise UserError(_('Choose between 1 and 2000 plots.'))
        vals = [{'name': '%s%s' % (self.prefix, self.start_number + i), 'property_id': self.property_id.id,
                 'unit_type': 'plot', 'area': self.area, 'area_unit_id': self.area_unit_id.id,
                 'land_use': self.land_use, 'plot_value': self.plot_value, 'service_charge_basis': 'excluded'}
                for i in range(self.count)]
        units = self.env['re.unit'].create(vals)
        self.property_id.message_post(body=_('%s plots created by subdivision.', len(units)))
        return self.property_id.action_view_units()
