# -*- coding: utf-8 -*-
"""Generic approval framework for sensitive real-estate transactions.

Every document that needs approval inherits ``re.approval.mixin`` and sets
``_re_approval_document_type``. The applicable ``re.approval.rule`` is the
active rule of that document type (company specific or shared) with the
highest ``min_amount`` that is lower than or equal to the document amount.
If no rule matches, no approval is required and the request is recorded as
auto-approved in the approval log.

Segregation of duties: when the rule requires it, the user who requested the
approval can never be the user who approves it (even if they belong to the
approver group).
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

DOCUMENT_TYPES = [
    ('lease', 'Lease Approval'),
    ('lease_amendment', 'Lease Amendment / Rental Change'),
    ('rent_concession', 'Rental Concession'),
    ('rent_escalation', 'Non-contractual Rent Escalation'),
    ('deposit_refund', 'Security Deposit Refund'),
    ('tenant_credit_note', 'Tenant Credit Note / Adjustment'),
    ('work_order', 'Maintenance Expenditure'),
    ('vendor_selection', 'Vendor Selection / Quotation'),
    ('capex', 'Capital Expenditure'),
    ('service_charge_budget', 'Service-Charge Budget'),
    ('valuation', 'Property Valuation'),
    ('investment', 'Investment Acquisition'),
    ('property_disposal', 'Property Disposal'),
]


class ReApprovalRule(models.Model):
    _name = 're.approval.rule'
    _description = 'Real Estate Approval Rule'
    _order = 'document_type, min_amount desc'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    document_type = fields.Selection(DOCUMENT_TYPES, required=True)
    company_id = fields.Many2one('res.company', help='Leave empty to apply to all companies.')
    min_amount = fields.Monetary(
        'Minimum Amount', currency_field='currency_id',
        help='The rule applies when the document amount is greater than or equal to this amount '
             '(expressed in the company currency). The matching rule with the highest minimum wins.')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    group_id = fields.Many2one('res.groups', 'Approver Group', required=True,
                               help='Users of this group (or implying it) can approve.')
    segregation = fields.Boolean('Segregation of Duties', default=True,
                                 help='The requester cannot approve their own request.')
    note = fields.Text('Policy Note')

    @api.model
    def _get_rule(self, document_type, amount, company):
        domain = [('document_type', '=', document_type), ('min_amount', '<=', amount or 0.0),
                  ('company_id', 'in', [False, company.id] if company else [False])]
        rules = self.sudo().search(domain)
        # company-specific rules take precedence over shared ones with the same threshold
        rules = rules.sorted(lambda r: (r.min_amount, bool(r.company_id)), reverse=True)
        return rules[:1]


class ReApprovalLog(models.Model):
    _name = 're.approval.log'
    _description = 'Real Estate Approval Audit Log'
    _order = 'date desc, id desc'
    _rec_name = 'document_name'

    res_model = fields.Char(required=True, index=True, readonly=True)
    res_id = fields.Integer(required=True, index=True, readonly=True)
    document_name = fields.Char(readonly=True)
    document_type = fields.Selection(DOCUMENT_TYPES, readonly=True)
    action = fields.Selection([
        ('requested', 'Requested'),
        ('auto_approved', 'Auto-approved (no rule)'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('override', 'Control Override'),
        ('reset', 'Reset to Draft'),
    ], required=True, readonly=True)
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user)
    date = fields.Datetime(readonly=True, default=fields.Datetime.now)
    amount = fields.Float(readonly=True)
    rule_id = fields.Many2one('re.approval.rule', readonly=True)
    note = fields.Text(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def write(self, vals):
        raise UserError(_('Approval audit log entries cannot be modified.'))

    def unlink(self):
        if not self.env.su:
            raise UserError(_('Approval audit log entries cannot be deleted.'))
        return super().unlink()

    def action_open_document(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model,
                'res_id': self.res_id, 'view_mode': 'form'}


class ReApprovalMixin(models.AbstractModel):
    _name = 're.approval.mixin'
    _description = 'Real Estate Approval Mixin'

    _re_approval_document_type = None

    re_approval_state = fields.Selection([
        ('none', 'Not Requested'),
        ('not_required', 'Not Required'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval Status', default='none', copy=False, tracking=True, readonly=True)
    re_approval_rule_id = fields.Many2one('re.approval.rule', 'Approval Rule', copy=False, readonly=True)
    re_approval_group_id = fields.Many2one(related='re_approval_rule_id.group_id', string='Approver Group')
    re_requested_by_id = fields.Many2one('res.users', 'Requested By', copy=False, readonly=True)
    re_requested_date = fields.Datetime('Requested On', copy=False, readonly=True)
    re_approved_by_id = fields.Many2one('res.users', 'Approved By', copy=False, readonly=True, tracking=True)
    re_approved_date = fields.Datetime('Approved On', copy=False, readonly=True)
    re_rejection_reason = fields.Text('Rejection Reason', copy=False, readonly=True)
    re_can_approve = fields.Boolean(compute='_compute_re_can_approve')
    re_approval_log_count = fields.Integer(compute='_compute_re_approval_log_count')

    # ------------------------------------------------------------------
    def _re_approval_amount(self):
        """Amount (company currency) used to select the approval rule."""
        return 0.0

    def _re_approval_company(self):
        return self.company_id if 'company_id' in self._fields and self.company_id else self.env.company

    def _re_approval_doc_type(self):
        return self._re_approval_document_type

    def _compute_re_can_approve(self):
        for rec in self:
            rule = rec.re_approval_rule_id
            rec.re_can_approve = bool(
                rec.re_approval_state == 'pending' and rule
                and rec._re_user_in_group(self.env.user, rule.group_id)
                and not (rule.segregation and rec.re_requested_by_id == self.env.user))

    def _compute_re_approval_log_count(self):
        Log = self.env['re.approval.log'].sudo()
        for rec in self:
            rec.re_approval_log_count = Log.search_count([('res_model', '=', rec._name), ('res_id', '=', rec.id)])

    def _re_log(self, action, amount=0.0, note=False, rule=False):
        Log = self.env['re.approval.log'].sudo()
        for rec in self:
            Log.create({
                'res_model': rec._name,
                'res_id': rec.id,
                'document_name': rec.display_name,
                'document_type': rec._re_approval_doc_type(),
                'action': action,
                'amount': amount,
                'note': note,
                'rule_id': rule.id if rule else False,
                'company_id': rec._re_approval_company().id,
                'user_id': self.env.user.id,
            })

    def _re_user_in_group(self, user, group):
        return group.sudo() in user.sudo().groups_id

    def _re_request_approval(self):
        """Returns True if approval is immediately granted (no rule)."""
        self.ensure_one()
        amount = self._re_approval_amount()
        rule = self.env['re.approval.rule']._get_rule(self._re_approval_doc_type(), amount, self._re_approval_company())
        now = fields.Datetime.now()
        if not rule:
            self.write({'re_approval_state': 'not_required', 're_approval_rule_id': False,
                        're_requested_by_id': self.env.uid, 're_requested_date': now,
                        're_approved_by_id': False, 're_approved_date': now, 're_rejection_reason': False})
            self._re_log('auto_approved', amount, _('No approval rule matched this amount.'))
            return True
        self.write({'re_approval_state': 'pending', 're_approval_rule_id': rule.id,
                    're_requested_by_id': self.env.uid, 're_requested_date': now,
                    're_approved_by_id': False, 're_approved_date': False, 're_rejection_reason': False})
        self._re_log('requested', amount, rule=rule)
        self._re_notify_approvers(rule)
        return False

    def _re_notify_approvers(self, rule):
        if not hasattr(self, 'activity_schedule'):
            return
        users = rule.group_id.sudo().users.filtered(
            lambda u: not u.share and u.active and self._re_approval_company() in u.company_ids)
        if rule.segregation:
            users -= self.env.user
        for user in users[:5]:
            self.sudo().activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id,
                summary=_('Approval required: %s', dict(DOCUMENT_TYPES).get(self._re_approval_doc_type())),
                note=_('Rule: %s', rule.name))

    def _re_check_can_approve(self):
        for rec in self:
            if rec.re_approval_state != 'pending':
                raise UserError(_('%s is not waiting for approval.', rec.display_name))
            rule = rec.re_approval_rule_id
            if not self.env.su and not rec._re_user_in_group(self.env.user, rule.group_id):
                raise AccessError(_('Only members of "%(group)s" can approve %(doc)s (rule: %(rule)s).',
                                    group=rule.group_id.full_name, doc=rec.display_name, rule=rule.name))
            if rule.segregation and rec.re_requested_by_id == self.env.user:
                raise AccessError(_('Segregation of duties: you requested approval of %s and cannot approve it yourself.',
                                    rec.display_name))

    def _re_approve(self, note=False):
        self._re_check_can_approve()
        for rec in self:
            rec.write({'re_approval_state': 'approved', 're_approved_by_id': self.env.uid,
                       're_approved_date': fields.Datetime.now()})
            rec._re_log('approved', rec._re_approval_amount(), note, rule=rec.re_approval_rule_id)
            if hasattr(rec, 'activity_ids'):
                rec.sudo().activity_ids.filtered(lambda a: (a.summary or '').startswith('Approval required')).action_feedback(
                    feedback=_('Approved by %s', self.env.user.name))

    def _re_reject(self, reason):
        if not reason:
            raise UserError(_('A rejection reason is required.'))
        self._re_check_can_approve()
        for rec in self:
            rec.write({'re_approval_state': 'rejected', 're_rejection_reason': reason})
            rec._re_log('rejected', rec._re_approval_amount(), reason, rule=rec.re_approval_rule_id)
            if hasattr(rec, 'activity_ids'):
                rec.sudo().activity_ids.filtered(lambda a: (a.summary or '').startswith('Approval required')).action_feedback(
                    feedback=_('Rejected by %(user)s: %(reason)s', user=self.env.user.name, reason=reason))

    def _re_is_approved(self):
        self.ensure_one()
        return self.re_approval_state in ('approved', 'not_required')

    def action_re_open_reject_wizard(self):
        self.ensure_one()
        self._re_check_can_approve()
        return {
            'type': 'ir.actions.act_window', 'name': _('Reject'), 'res_model': 're.reject.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    def action_re_view_approval_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Approval History'), 'res_model': 're.approval.log',
            'view_mode': 'list,form', 'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
        }

    def _re_after_reject(self):
        """Hook for documents to change their own state after rejection."""
        return True
