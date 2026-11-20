# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

UTILITY_TYPES = [
    ('electricity', 'Electricity'),
    ('water', 'Water'),
    ('generator_fuel', 'Generator Fuel'),
    ('solar', 'Solar Electricity'),
    ('gas', 'Gas'),
    ('waste', 'Waste Management'),
    ('equipment_hours', 'Equipment Run-hours'),
]


class ReUtilityTariff(models.Model):
    _name = 're.utility.tariff'
    _description = 'Utility Tariff'
    _order = 'utility_type, name'

    name = fields.Char(required=True)
    utility_type = fields.Selection(UTILITY_TYPES, required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    uom_label = fields.Char('Unit', default='kWh')
    rate = fields.Float('Rate per Unit', required=True, digits=(16, 4))
    fixed_charge = fields.Monetary('Fixed Charge per Reading')
    date_from = fields.Date()
    active = fields.Boolean(default=True)
    note = fields.Text(help='Source of the tariff (e.g. utility provider schedule, landlord recovery policy).')


class ReMeter(models.Model):
    _name = 're.meter'
    _description = 'Utility Meter'
    _inherit = ['mail.thread']
    _order = 'property_id, name'

    name = fields.Char('Meter Number', required=True, tracking=True)
    utility_type = fields.Selection(UTILITY_TYPES, required=True, default='electricity')
    scope = fields.Selection([('tenant', 'Tenant Sub-meter'), ('common', 'Common Area'), ('main', 'Main / Bulk Meter')],
                             default='tenant', required=True)
    property_id = fields.Many2one('re.property', required=True, index=True)
    building_id = fields.Many2one('re.building', domain="[('property_id', '=', property_id)]")
    unit_id = fields.Many2one('re.unit', domain="[('property_id', '=', property_id)]")
    equipment_id = fields.Many2one('maintenance.equipment', 'Equipment (run-hour meter)')
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    tariff_id = fields.Many2one('re.utility.tariff', domain="[('utility_type', '=', utility_type)]")
    multiplier = fields.Float(default=1.0, help='CT ratio or conversion factor.')
    initial_reading = fields.Float()
    active = fields.Boolean(default=True)
    external_ref = fields.Char('Smart Meter / BMS ID', index=True,
                               help='Identifier used by an external smart-meter or BMS integration.')
    prepaid = fields.Boolean('Prepaid (e.g. LUKU)', help='Prepaid meters are paid directly by the tenant and are '
                                                         'not recharged.')
    reading_ids = fields.One2many('re.meter.reading', 'meter_id')
    last_reading = fields.Float(compute='_compute_last')
    last_reading_date = fields.Date(compute='_compute_last')

    _sql_constraints = [('name_company_uniq', 'unique(name, utility_type, property_id)', 'Meter already registered.')]

    def _compute_last(self):
        for rec in self:
            last = rec.reading_ids.sorted(lambda r: (r.date, r.id), reverse=True)[:1]
            rec.last_reading = last.current_reading if last else rec.initial_reading
            rec.last_reading_date = last.date

    @api.constrains('unit_id', 'building_id', 'property_id')
    def _check_location(self):
        for rec in self:
            if rec.unit_id and rec.unit_id.property_id != rec.property_id:
                raise ValidationError(_('The unit does not belong to the property.'))


class ReMeterReading(models.Model):
    _name = 're.meter.reading'
    _description = 'Meter Reading'
    _order = 'date desc, id desc'

    meter_id = fields.Many2one('re.meter', required=True, index=True, ondelete='restrict')
    utility_type = fields.Selection(related='meter_id.utility_type', store=True)
    property_id = fields.Many2one(related='meter_id.property_id', store=True, index=True)
    building_id = fields.Many2one(related='meter_id.building_id', store=True)
    unit_id = fields.Many2one(related='meter_id.unit_id', store=True)
    company_id = fields.Many2one(related='meter_id.company_id', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    previous_reading = fields.Float(compute='_compute_previous', store=True, readonly=False)
    current_reading = fields.Float(required=True)
    rollover = fields.Boolean('Meter Replaced / Rolled Over',
                              help='Allows a current reading lower than the previous one.')
    consumption = fields.Float(compute='_compute_cost', store=True)
    tariff_id = fields.Many2one('re.utility.tariff', compute='_compute_tariff', store=True, readonly=False)
    currency_id = fields.Many2one(related='tariff_id.currency_id')
    rate = fields.Float(digits=(16, 4), compute='_compute_tariff', store=True, readonly=False)
    cost = fields.Monetary(compute='_compute_cost', store=True)
    lease_id = fields.Many2one('re.lease', compute='_compute_lease', store=True, readonly=False)
    tenant_id = fields.Many2one(related='lease_id.tenant_id', store=True)
    billable = fields.Boolean(compute='_compute_lease', store=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('billed', 'Billed'),
                              ('not_billable', 'Not Recharged')], default='draft', index=True)
    invoice_line_id = fields.Many2one('account.move.line', readonly=True, copy=False)
    invoice_id = fields.Many2one(related='invoice_line_id.move_id', store=True)
    source = fields.Selection([('manual', 'Manual'), ('import', 'Import'), ('api', 'Smart Meter / API')],
                              default='manual')
    external_id = fields.Char(index=True)
    photo = fields.Image(max_width=1024, max_height=1024)

    _sql_constraints = [
        ('meter_date_uniq', 'unique(meter_id, date)', 'Only one reading per meter per date.'),
        ('external_uniq', 'unique(meter_id, external_id)', 'Duplicate external reading.'),
    ]

    @api.depends('meter_id', 'date')
    def _compute_previous(self):
        for rec in self:
            if not rec.meter_id or not rec.date:
                rec.previous_reading = 0.0
                continue
            prev = self.search([('meter_id', '=', rec.meter_id.id), ('date', '<', rec.date),
                                ('id', '!=', rec._origin.id or 0)], order='date desc, id desc', limit=1)
            rec.previous_reading = prev.current_reading if prev else rec.meter_id.initial_reading

    @api.depends('meter_id.tariff_id')
    def _compute_tariff(self):
        for rec in self:
            rec.tariff_id = rec.meter_id.tariff_id
            rec.rate = rec.meter_id.tariff_id.rate

    @api.depends('previous_reading', 'current_reading', 'rate', 'meter_id.multiplier', 'tariff_id.fixed_charge')
    def _compute_cost(self):
        for rec in self:
            rec.consumption = (rec.current_reading - rec.previous_reading) * (rec.meter_id.multiplier or 1.0)
            rec.cost = rec.consumption * rec.rate + (rec.tariff_id.fixed_charge or 0.0) if rec.consumption else 0.0

    @api.depends('meter_id', 'date')
    def _compute_lease(self):
        for rec in self:
            lease = self.env['re.lease']
            if rec.meter_id.unit_id and rec.date and rec.meter_id.scope == 'tenant':
                lease = self.env['re.lease'].search([
                    ('unit_ids', 'in', rec.meter_id.unit_id.id),
                    ('state', 'in', ('active', 'expiring', 'terminated', 'expired', 'renewed')),
                    ('date_start', '<=', rec.date), ('effective_end_date', '>=', rec.date)], limit=1)
            rec.lease_id = lease
            rec.billable = bool(lease and lease.utility_recharge and not rec.meter_id.prepaid
                                and rec.meter_id.utility_type not in ('equipment_hours',))

    @api.constrains('current_reading', 'previous_reading', 'rollover')
    def _check_reading(self):
        for rec in self:
            if rec.current_reading < rec.previous_reading and not rec.rollover:
                raise ValidationError(_('Reading %(cur)s on meter %(m)s is lower than the previous reading %(prev)s. '
                                        'Tick "Meter Replaced / Rolled Over" if correct.',
                                        cur=rec.current_reading, m=rec.meter_id.name, prev=rec.previous_reading))

    def write(self, vals):
        if self.filtered(lambda r: r.state == 'billed') and set(vals) & {'current_reading', 'previous_reading', 'rate', 'meter_id', 'date'}:
            raise UserError(_('Billed readings cannot be modified. Record a correcting reading and credit note.'))
        return super().write(vals)

    def action_confirm(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.state = 'confirmed' if rec.billable else 'not_billable'

    def action_bill(self):
        """Bill confirmed, billable readings through native customer invoices
        (one invoice per lease). Idempotent: billed readings are skipped."""
        self.action_confirm()
        readings = self.filtered(lambda r: r.state == 'confirmed' and r.billable and not r.invoice_line_id)
        by_lease = defaultdict(lambda: self.browse())
        for r in readings:
            by_lease[r.lease_id] |= r
        moves = self.env['account.move']
        for lease, group in by_lease.items():
            company = lease.company_id
            product = company._re_get_product('utility')
            journal = company.re_rental_journal_id or self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
            today = fields.Date.context_today(self)
            lines = []
            for r in group:
                lines.append((0, 0, {
                    'product_id': product.id, 'quantity': 1, 'price_unit': r.currency_id._convert(
                        r.cost, lease.currency_id, company, r.date) if r.currency_id else r.cost,
                    'name': _('%(type)s meter %(meter)s: %(prev)s -> %(cur)s = %(cons)s %(uom)s @ %(rate)s',
                              type=dict(UTILITY_TYPES)[r.utility_type], meter=r.meter_id.name,
                              prev=r.previous_reading, cur=r.current_reading, cons=round(r.consumption, 3),
                              uom=r.tariff_id.uom_label or '', rate=r.rate),
                    'analytic_distribution': lease.property_id._re_analytic_distribution(lease.building_id),
                    're_charge_type': 'utility', 're_meter_reading_id': r.id,
                }))
            move = self.env['account.move'].with_company(company).create({
                'move_type': 'out_invoice', 'partner_id': lease.tenant_id.id, 'invoice_date': today,
                'journal_id': journal.id, 'currency_id': lease.currency_id.id, 're_lease_id': lease.id,
                'invoice_origin': lease.name, 'ref': _('Utility recharge %s', lease.name),
                'invoice_date_due': today + timedelta(days=lease.payment_due_days or 0),
                'invoice_line_ids': lines,
            })
            for r in group:
                r.write({'invoice_line_id': move.invoice_line_ids.filtered(lambda l: l.re_meter_reading_id == r)[:1].id,
                         'state': 'billed'})
            if company.re_auto_post_invoices:
                move.action_post()
            moves |= move
        if not moves:
            raise UserError(_('No confirmed, billable readings to invoice.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('id', 'in', moves.ids)], 'name': _('Utility Invoices')}

    @api.model
    def api_submit_readings(self, readings):
        """Integration point for smart meters / BMS middleware (JSON-RPC / XML-RPC).

        ``readings``: list of dicts {meter_ref, date (YYYY-MM-DD), value, external_id}.
        The calling integration user needs Real Estate Property Manager rights.
        Returns a list of {external_id, status, message}. Duplicate external ids
        are ignored (idempotent). No external vendor is connected out of the box."""
        results = []
        Meter = self.env['re.meter']
        for item in readings or []:
            ext = str(item.get('external_id') or '')
            try:
                meter = Meter.search([('external_ref', '=', item.get('meter_ref'))], limit=1)
                if not meter:
                    raise ValidationError(_('Unknown meter %s', item.get('meter_ref')))
                if ext and self.search_count([('meter_id', '=', meter.id), ('external_id', '=', ext)]):
                    results.append({'external_id': ext, 'status': 'duplicate', 'message': 'Already received'})
                    continue
                with self.env.cr.savepoint():
                    self.create({'meter_id': meter.id, 'date': item['date'], 'current_reading': float(item['value']),
                                 'source': 'api', 'external_id': ext or False})
                results.append({'external_id': ext, 'status': 'ok', 'message': ''})
            except Exception as e:  # noqa: BLE001 - returned to the caller as an error status
                results.append({'external_id': ext, 'status': 'error', 'message': str(e)})
        return results
