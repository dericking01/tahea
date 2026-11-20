# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.sql import column_exists, create_column

RE_CHARGE_TYPES = [
    ('rent', 'Rent'),
    ('service_charge', 'Service Charge'),
    ('service_charge_recon', 'Service-Charge Reconciliation'),
    ('parking', 'Parking'),
    ('marketing_levy', 'Marketing Levy'),
    ('utility_fixed', 'Fixed Utility Charge'),
    ('utility', 'Utility Recharge (metered)'),
    ('turnover_rent', 'Turnover Rent'),
    ('other', 'Other Contractual Fee'),
    ('concession', 'Rent Concession'),
    ('deposit', 'Security Deposit (liability)'),
    ('deposit_deduction', 'Deposit Deduction'),
]


def _precreate_columns(cr, table, columns):
    """Create stored computed columns up-front so installing the module on a
    database with millions of journal items does not recompute them for every
    historical row (they are filled for new / changed records only)."""
    for name, sqltype in columns:
        if not column_exists(cr, table, name):
            create_column(cr, table, name, sqltype)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 're.approval.mixin']
    _re_approval_document_type = 'tenant_credit_note'

    re_lease_id = fields.Many2one('re.lease', 'Lease', index=True, copy=True, tracking=True)
    re_property_id = fields.Many2one('re.property', 'Property', compute='_compute_re_location', store=True,
                                     index=True)
    re_building_id = fields.Many2one('re.building', 'Building', compute='_compute_re_location', store=True)
    re_work_order_id = fields.Many2one('re.work.order', 'Work Order', compute='_compute_re_work_order',
                                       store=True, readonly=False, index=True, copy=False, tracking=True)
    re_deposit_id = fields.Many2one('re.security.deposit', 'Security Deposit', index=True, copy=False)
    re_turnover_report_id = fields.Many2one('re.turnover.report', copy=False)
    re_dispute_state = fields.Selection([('none', 'No Dispute'), ('open', 'Disputed'), ('resolved', 'Resolved'),
                                         ('rejected', 'Dispute Rejected')], 'Dispute', default='none', copy=False,
                                        tracking=True)
    re_dispute_reason = fields.Char('Dispute Reason', copy=False)
    re_dispute_ticket_id = fields.Many2one('re.tenant.ticket', copy=False)
    re_is_tenant_document = fields.Boolean(compute='_compute_re_is_tenant_document')

    def _auto_init(self):
        _precreate_columns(self.env.cr, 'account_move', [
            ('re_property_id', 'int4'), ('re_building_id', 'int4'), ('re_work_order_id', 'int4')])
        return super()._auto_init()

    @api.depends('re_lease_id', 'line_ids.re_property_id', 'line_ids.re_building_id')
    def _compute_re_location(self):
        for move in self:
            if move.re_lease_id:
                move.re_property_id = move.re_lease_id.property_id
                move.re_building_id = move.re_lease_id.building_id
            else:
                move.re_property_id = move.line_ids.re_property_id[:1]
                move.re_building_id = move.line_ids.re_building_id[:1]

    @api.depends('invoice_line_ids.purchase_line_id')
    def _compute_re_work_order(self):
        for move in self:
            wo = move.invoice_line_ids.purchase_line_id.order_id.re_work_order_id[:1]
            move.re_work_order_id = wo or move.re_work_order_id

    def _compute_re_is_tenant_document(self):
        for move in self:
            move.re_is_tenant_document = bool(move.re_lease_id or move.partner_id.commercial_partner_id.re_is_tenant)

    def _re_approval_amount(self):
        return abs(self.amount_total_signed)

    # ------------------------------------------------------------------
    def action_re_request_adjustment_approval(self):
        for move in self:
            if move.move_type != 'out_refund':
                raise UserError(_('Adjustment approval applies to customer credit notes.'))
            if move._re_request_approval():
                move.message_post(body=_('No approval rule applies to this credit note amount.'))

    def action_re_approve_adjustment(self):
        self._re_approve()

    def _re_check_post_controls(self):
        fm = self.env.user.has_group('real_estate_lifecycle.group_re_finance_manager')
        for move in self:
            company = move.company_id
            if move.move_type == 'out_refund' and move.re_is_tenant_document and not move.re_deposit_id:
                if company.re_block_unapproved_tenant_credit and move.re_approval_state not in ('approved', 'not_required'):
                    raise UserError(_('Credit note %s to a tenant requires adjustment approval before posting.',
                                      move.display_name))
            if move.move_type == 'in_invoice' and move.re_work_order_id:
                wo = move.re_work_order_id
                reasons = []
                if not wo._re_is_approved() and not wo.is_emergency:
                    reasons.append(_('work order %s has no approved budget', wo.name))
                others = wo.vendor_bill_ids.filtered(lambda m: m.state == 'posted' and m != move)
                total = -sum(others.mapped('amount_untaxed_signed')) - move.amount_untaxed_signed
                limit = wo.approved_budget * (1 + company.re_bill_tolerance_pct / 100.0)
                if wo.approved_budget and total > limit + 0.005:
                    reasons.append(_('total billed %(t)s exceeds approved %(a)s (+%(p)s%% tolerance)',
                                     t=wo.currency_id.format(total), a=wo.currency_id.format(wo.approved_budget),
                                     p=company.re_bill_tolerance_pct))
                if not reasons:
                    continue
                text = '; '.join(reasons)
                if company.re_block_bill_over_approved and not fm and not self.env.su:
                    raise UserError(_('Vendor bill %(b)s cannot be posted: %(r)s. A Finance Manager may override, or '
                                      'request a supplementary approval on the work order.', b=move.display_name, r=text))
                exc = self.env['re.exception']._re_raise(
                    'control_override', move, company,
                    _('Vendor bill %(b)s posted by %(u)s despite control: %(r)s.', b=move.display_name,
                      u=self.env.user.name, r=text), prop=wo.property_id, amount=total - wo.approved_budget)
                wo._re_log('override', total, text)
                move.message_post(body=_('Control override recorded: %s', exc.name))

    def _post(self, soft=True):
        self._re_check_post_controls()
        return super()._post(soft)

    def action_re_open_lease(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 're.lease', 'res_id': self.re_lease_id.id,
                'view_mode': 'form'}


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    re_property_id = fields.Many2one('re.property', 'Property', compute='_compute_re_dimensions', store=True,
                                     index=True, help='Derived from the analytic distribution (Properties plan).')
    re_building_id = fields.Many2one('re.building', 'Building', compute='_compute_re_dimensions', store=True,
                                     index=True)
    re_lease_id = fields.Many2one(related='move_id.re_lease_id', store=True, string='Lease', index=True)
    re_schedule_line_id = fields.Many2one('re.billing.schedule', 'Billing Obligation', index=True, copy=False)
    re_charge_type = fields.Selection(RE_CHARGE_TYPES, 'RE Charge Type', index=True)
    re_period_start = fields.Date('Billing Period Start')
    re_period_end = fields.Date('Billing Period End')
    re_service_charge_budget_id = fields.Many2one('re.service.charge.budget', index=True)
    re_meter_reading_id = fields.Many2one('re.meter.reading', copy=False)

    def _auto_init(self):
        _precreate_columns(self.env.cr, 'account_move_line', [
            ('re_property_id', 'int4'), ('re_building_id', 'int4'), ('re_lease_id', 'int4')])
        return super()._auto_init()

    @api.depends('analytic_distribution')
    def _compute_re_dimensions(self):
        all_ids = set()
        for line in self:
            for key in (line.analytic_distribution or {}):
                all_ids.update(int(i) for i in str(key).split(',') if i.isdigit())
        props = {}
        blds = {}
        if all_ids:
            for p in self.env['re.property'].sudo().with_context(active_test=False).search(
                    [('analytic_account_id', 'in', list(all_ids))]):
                props[p.analytic_account_id.id] = p.id
            for b in self.env['re.building'].sudo().with_context(active_test=False).search(
                    [('analytic_account_id', 'in', list(all_ids))]):
                blds[b.analytic_account_id.id] = b
        for line in self:
            prop = building = False
            for key in (line.analytic_distribution or {}):
                for i in str(key).split(','):
                    if not i.isdigit():
                        continue
                    i = int(i)
                    prop = prop or props.get(i)
                    if not building and i in blds:
                        building = blds[i]
            if building and not prop:
                prop = building.property_id.id
            line.re_property_id = prop
            line.re_building_id = building.id if building else False
