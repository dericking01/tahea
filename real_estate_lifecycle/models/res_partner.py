# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ---- Tenant profile ------------------------------------------------------------
    re_is_tenant = fields.Boolean('Tenant', index=True, copy=False)
    re_tenant_type = fields.Selection([('individual', 'Individual'), ('company', 'Company'),
                                       ('government', 'Government / Institution'), ('ngo', 'NGO')], 'Tenant Type')
    re_id_type = fields.Selection([('nida', 'NIDA National ID'), ('passport', 'Passport'), ('voter', "Voter's ID"),
                                   ('driving', 'Driving Licence'), ('brela', 'BRELA Certificate'),
                                   ('other', 'Other')], 'ID Document')
    re_id_number = fields.Char('ID / Registration No.')
    re_emergency_contact = fields.Char('Emergency Contact')
    re_lease_ids = fields.One2many('re.lease', 'tenant_id', 'Leases')
    re_lease_count = fields.Integer(compute='_compute_re_tenant_stats')
    re_ticket_count = fields.Integer(compute='_compute_re_tenant_stats')
    re_on_time_rate = fields.Float('On-time Payment Rate (%)', compute='_compute_re_tenant_stats')
    re_avg_days_late = fields.Float('Average Days Late', compute='_compute_re_tenant_stats')

    # ---- Contractor profile -------------------------------------------------------
    re_is_contractor = fields.Boolean('Contractor / Service Vendor', index=True)
    re_service_category_ids = fields.Many2many('re.service.category', string='Service Categories')
    re_registration_number = fields.Char('Company Registration No. (BRELA)')
    re_tin = fields.Char('TIN')
    re_license_ids = fields.One2many('re.vendor.license', 'partner_id', 'Licences')
    re_insurance_provider = fields.Char('Insurance Provider')
    re_insurance_policy = fields.Char('Insurance Policy No.')
    re_insurance_expiry = fields.Date('Insurance Expiry')
    re_contract_ids = fields.One2many('re.vendor.contract', 'partner_id', 'Contracts')
    re_is_compliant = fields.Boolean('Compliant', compute='_compute_re_compliance')
    re_compliance_note = fields.Char(compute='_compute_re_compliance')
    re_jobs_assigned = fields.Integer('Jobs Assigned', compute='_compute_re_performance')
    re_jobs_completed = fields.Integer('Jobs Completed', compute='_compute_re_performance')
    re_on_time_completion = fields.Float('On-time Completion (%)', compute='_compute_re_performance')
    re_avg_completion_days = fields.Float('Avg Completion (days)', compute='_compute_re_performance')
    re_repeat_faults = fields.Integer('Repeat Faults', compute='_compute_re_performance')
    re_complaints = fields.Integer('Poor Ratings (<=2)', compute='_compute_re_performance')
    re_avg_rating = fields.Float('Average Tenant Rating', compute='_compute_re_performance')
    re_approved_spend = fields.Monetary('Approved Budget', compute='_compute_re_performance',
                                        currency_field='re_company_currency_id')
    re_actual_spend = fields.Monetary('Actual Billed', compute='_compute_re_performance',
                                      currency_field='re_company_currency_id')
    re_cost_variance_pct = fields.Float('Actual vs Approved (%)', compute='_compute_re_performance')
    re_company_currency_id = fields.Many2one('res.currency', compute='_compute_re_company_currency')

    def _compute_re_company_currency(self):
        for rec in self:
            rec.re_company_currency_id = self.env.company.currency_id

    def _compute_re_compliance(self):
        today = fields.Date.context_today(self)
        for rec in self:
            issues = []
            if rec.re_is_contractor:
                expired = rec.re_license_ids.filtered(lambda l: l.expiry_date and l.expiry_date < today)
                if expired:
                    issues.append(_('expired licence(s): %s', ', '.join(expired.mapped('number'))))
                if rec.re_insurance_expiry and rec.re_insurance_expiry < today:
                    issues.append(_('insurance expired on %s', rec.re_insurance_expiry))
            rec.re_is_compliant = not issues
            rec.re_compliance_note = '; '.join(issues)

    def _compute_re_tenant_stats(self):
        Lease = self.env['re.lease']
        Ticket = self.env['re.tenant.ticket']
        AML = self.env['account.move.line'].sudo()
        for rec in self:
            if not rec.re_is_tenant:
                rec.re_lease_count = rec.re_ticket_count = 0
                rec.re_on_time_rate = rec.re_avg_days_late = 0.0
                continue
            rec.re_lease_count = Lease.search_count([('tenant_id', '=', rec.id)])
            rec.re_ticket_count = Ticket.search_count([('partner_id', '=', rec.id)])
            lines = AML.search([('partner_id', '=', rec.id), ('account_id.account_type', '=', 'asset_receivable'),
                                ('parent_state', '=', 'posted'), ('reconciled', '=', True), ('debit', '>', 0),
                                ('move_id.re_lease_id', '!=', False)], limit=200, order='date desc')
            late_days = []
            for line in lines:
                paid_on = max(line.matched_credit_ids.mapped('max_date') or [line.date])
                late_days.append(max(0, (paid_on - (line.date_maturity or line.date)).days))
            rec.re_on_time_rate = 100.0 * len([d for d in late_days if d == 0]) / len(late_days) if late_days else 0.0
            rec.re_avg_days_late = sum(late_days) / len(late_days) if late_days else 0.0

    def _compute_re_performance(self):
        WO = self.env['re.work.order']
        for rec in self:
            if not rec.re_is_contractor:
                rec.update({'re_jobs_assigned': 0, 're_jobs_completed': 0, 're_on_time_completion': 0.0,
                            're_avg_completion_days': 0.0, 're_repeat_faults': 0, 're_complaints': 0,
                            're_avg_rating': 0.0, 're_approved_spend': 0.0, 're_actual_spend': 0.0,
                            're_cost_variance_pct': 0.0})
                continue
            wos = WO.search([('contractor_id', 'child_of', rec.commercial_partner_id.id), ('state', '!=', 'cancelled')])
            done = wos.filtered('date_done')
            rated = wos.filtered('tenant_rating')
            approved = sum(wos.mapped('approved_budget'))
            actual = sum(wos.mapped('actual_cost'))
            rec.re_jobs_assigned = len(wos)
            rec.re_jobs_completed = len(done)
            rec.re_on_time_completion = 100.0 * len(done.filtered('on_time')) / len(done) if done else 0.0
            rec.re_avg_completion_days = sum(done.mapped('completion_days')) / len(done) if done else 0.0
            rec.re_repeat_faults = len(wos.filtered('is_repeat_fault'))
            rec.re_complaints = len(rated.filtered(lambda w: int(w.tenant_rating) <= 2))
            rec.re_avg_rating = sum(int(w.tenant_rating) for w in rated) / len(rated) if rated else 0.0
            rec.re_approved_spend = approved
            rec.re_actual_spend = actual
            rec.re_cost_variance_pct = 100.0 * (actual - approved) / approved if approved else 0.0

    def action_re_view_leases(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_lease')
        action['domain'] = [('tenant_id', '=', self.id)]
        action['context'] = {'default_tenant_id': self.id}
        return action

    def action_re_view_tickets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_ticket')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action

    def action_re_view_work_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_work_order')
        action['domain'] = [('contractor_id', 'child_of', self.commercial_partner_id.id)]
        return action

    def action_re_print_statement(self):
        return self.env.ref('real_estate_lifecycle.action_report_tenant_statement').report_action(self)

    def _re_statement_data(self, date_from=None, date_to=None):
        """Tenant account statement from native receivable lines (opening balance,
        invoices, credit notes, payments, running balance)."""
        self.ensure_one()
        AML = self.env['account.move.line'].sudo()
        date_to = date_to or fields.Date.context_today(self)
        base = [('partner_id', 'child_of', self.commercial_partner_id.id),
                ('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted')]
        opening = 0.0
        if date_from:
            opening = sum(AML.search(base + [('date', '<', date_from)]).mapped('balance'))
            base.append(('date', '>=', date_from))
        lines = AML.search(base + [('date', '<=', date_to)], order='date, id')
        running = opening
        rows = []
        for line in lines:
            running += line.balance
            rows.append({'date': line.date, 'ref': line.move_id.name, 'label': line.move_id.ref or line.name or '',
                         'due': line.date_maturity, 'debit': line.debit, 'credit': line.credit, 'balance': running,
                         'disputed': line.move_id.re_dispute_state == 'open'})
        return {'opening': opening, 'rows': rows, 'closing': running, 'date_from': date_from, 'date_to': date_to}
