# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ReTurnoverReport(models.Model):
    """Tenant sales report used for turnover-based rent.

    Formula (documented on every record in ``calculation_note``):
        excess_sales = max(0, gross_sales - breakpoint)
        percentage_rent = excess_sales * rate
        greater_of mode : turnover_rent = max(0, percentage_rent - base_rent_billed_for_period)
        additional mode : turnover_rent = percentage_rent
    Only *verified* sales figures can be invoiced. Rate, breakpoint and mode are
    copied from the lease at verification so later lease amendments do not
    change historical calculations."""
    _name = 're.turnover.report'
    _description = 'Tenant Turnover (Sales) Report'
    _inherit = ['mail.thread']
    _order = 'period_start desc'

    name = fields.Char(compute='_compute_name', store=True)
    lease_id = fields.Many2one('re.lease', required=True, index=True,
                               domain="[('turnover_rent_enabled', '=', True)]")
    company_id = fields.Many2one(related='lease_id.company_id', store=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    tenant_id = fields.Many2one(related='lease_id.tenant_id', store=True)
    property_id = fields.Many2one(related='lease_id.property_id', store=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    gross_sales = fields.Monetary(required=True, tracking=True)
    source = fields.Selection([('tenant', 'Tenant Declaration'), ('audited', 'Audited Statement'),
                               ('pos', 'POS / EFD Data')], default='tenant', required=True)
    state = fields.Selection([('draft', 'Draft'), ('verified', 'Verified'), ('invoiced', 'Invoiced')],
                             default='draft', tracking=True)
    verified_by_id = fields.Many2one('res.users', readonly=True)
    verified_date = fields.Datetime(readonly=True)
    rate = fields.Float('Rate (%)', readonly=True)
    breakpoint = fields.Monetary(readonly=True)
    mode = fields.Selection([('greater_of', 'Greater of'), ('additional', 'Additional')], readonly=True)
    base_rent_billed = fields.Monetary(readonly=True)
    turnover_rent = fields.Monetary(readonly=True, tracking=True)
    calculation_note = fields.Text(readonly=True)
    invoice_id = fields.Many2one('account.move', readonly=True, copy=False)

    _sql_constraints = [('period_uniq', 'unique(lease_id, period_start)', 'A turnover report already exists for this period.')]

    @api.depends('lease_id', 'period_start', 'period_end')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s %s/%s' % (rec.lease_id.name or '', rec.period_start or '', rec.period_end or '')

    @api.constrains('period_start', 'period_end', 'gross_sales')
    def _check(self):
        for rec in self:
            if rec.period_end < rec.period_start:
                raise ValidationError(_('Period end must be after period start.'))
            if rec.gross_sales < 0:
                raise ValidationError(_('Gross sales cannot be negative.'))

    def write(self, vals):
        if self.filtered(lambda r: r.state != 'draft') and set(vals) & {'gross_sales', 'period_start', 'period_end', 'lease_id'}:
            raise UserError(_('Verified turnover reports cannot be changed.'))
        return super().write(vals)

    def action_verify(self):
        for rec in self:
            lease = rec.lease_id
            if not lease.turnover_rent_enabled:
                raise UserError(_('Lease %s has no turnover rent clause.', lease.name))
            rent_lines = lease.schedule_ids.filtered(
                lambda s: s.charge_type == 'rent' and s.period_start <= rec.period_end and s.period_end >= rec.period_start)
            base = 0.0
            for sl in rent_lines:
                overlap_start = max(sl.period_start, rec.period_start)
                overlap_end = min(sl.period_end, rec.period_end)
                days = (sl.period_end - sl.period_start).days + 1
                base += sl.amount * ((overlap_end - overlap_start).days + 1) / days
            base = rec.currency_id.round(base)
            excess = max(0.0, rec.gross_sales - lease.turnover_breakpoint)
            pct_rent = rec.currency_id.round(excess * lease.turnover_rate / 100.0)
            due = max(0.0, pct_rent - base) if lease.turnover_mode == 'greater_of' else pct_rent
            note = _(
                'Gross sales %(sales)s - breakpoint %(bp)s = %(excess)s; x %(rate)s%% = %(pct)s. '
                'Mode: %(mode)s. Base rent billed for the period: %(base)s. Turnover rent due: %(due)s.',
                sales=rec.currency_id.format(rec.gross_sales), bp=rec.currency_id.format(lease.turnover_breakpoint),
                excess=rec.currency_id.format(excess), rate=lease.turnover_rate, pct=rec.currency_id.format(pct_rent),
                mode=dict(lease._fields['turnover_mode'].selection)[lease.turnover_mode],
                base=rec.currency_id.format(base), due=rec.currency_id.format(due))
            rec.write({'state': 'verified', 'verified_by_id': self.env.uid, 'verified_date': fields.Datetime.now(),
                       'rate': lease.turnover_rate, 'breakpoint': lease.turnover_breakpoint,
                       'mode': lease.turnover_mode, 'base_rent_billed': base, 'turnover_rent': due,
                       'calculation_note': note})

    def action_create_invoice(self):
        for rec in self:
            if rec.state != 'verified':
                raise UserError(_('Only verified turnover reports can be invoiced.'))
            if rec.invoice_id and rec.invoice_id.state != 'cancel':
                raise UserError(_('Turnover report already invoiced.'))
            if rec.currency_id.is_zero(rec.turnover_rent):
                rec.state = 'invoiced'
                continue
            lease = rec.lease_id
            product = lease.company_id._re_get_product('turnover_rent')
            journal = lease.company_id.re_rental_journal_id or self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', lease.company_id.id)], limit=1)
            today = fields.Date.context_today(self)
            move = self.env['account.move'].with_company(lease.company_id).create({
                'move_type': 'out_invoice', 'partner_id': lease.tenant_id.id, 'invoice_date': today,
                'journal_id': journal.id, 'currency_id': lease.currency_id.id, 're_lease_id': lease.id,
                'invoice_origin': lease.name, 're_turnover_report_id': rec.id,
                'invoice_date_due': today + timedelta(days=lease.payment_due_days or 0),
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id, 'quantity': 1, 'price_unit': rec.turnover_rent,
                    'name': _('Turnover rent %(s)s - %(e)s', s=rec.period_start, e=rec.period_end),
                    'analytic_distribution': lease.property_id._re_analytic_distribution(lease.building_id),
                    're_charge_type': 'turnover_rent', 're_period_start': rec.period_start,
                    're_period_end': rec.period_end})],
            })
            rec.write({'invoice_id': move.id, 'state': 'invoiced'})
            if lease.company_id.re_auto_post_invoices:
                move.action_post()
