# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

WO_STATES = [
    ('new', 'New Request'),
    ('triage', 'Triage'),
    ('approval', 'Awaiting Approval'),
    ('assigned', 'Assigned'),
    ('in_progress', 'In Progress'),
    ('pending', 'Pending Parts / Contractor'),
    ('completed', 'Completed'),
    ('tenant_confirmation', 'Tenant Confirmation'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]
DONE_STATES = ('completed', 'tenant_confirmation', 'closed', 'cancelled')


class ReWorkOrder(models.Model):
    _name = 're.work.order'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 're.approval.mixin', 'portal.mixin']
    _order = 'priority desc, date_request desc, id desc'
    _re_approval_document_type = 'work_order'

    name = fields.Char('Work Order', required=True, copy=False, readonly=True, default='/', index=True)
    title = fields.Char('Problem', required=True, tracking=True)
    state = fields.Selection(WO_STATES, default='new', required=True, tracking=True, index=True, copy=False)
    property_id = fields.Many2one('re.property', required=True, index=True, tracking=True)
    building_id = fields.Many2one('re.building', domain="[('property_id', '=', property_id)]")
    floor_id = fields.Many2one('re.floor', domain="[('building_id', '=', building_id)]")
    unit_id = fields.Many2one('re.unit', domain="[('property_id', '=', property_id)]")
    equipment_id = fields.Many2one('maintenance.equipment', domain="[('re_property_id', '=', property_id)]",
                                   tracking=True)
    company_id = fields.Many2one(related='property_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    manager_id = fields.Many2one(related='property_id.manager_id', store=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'), ('corrective', 'Corrective'), ('predictive', 'Predictive'),
        ('emergency', 'Emergency')], required=True, default='corrective', tracking=True)
    category_id = fields.Many2one('re.maintenance.category')
    expenditure_type = fields.Selection([('opex', 'Operating Expense (OPEX)'), ('capex', 'Capital Expenditure (CAPEX)')],
                                        default='opex', required=True, tracking=True)
    description = fields.Html()
    priority = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent')], default='1',
                                tracking=True)
    requested_by_partner_id = fields.Many2one('res.partner', 'Requested By (Tenant / Contact)')
    requested_by_user_id = fields.Many2one('res.users', 'Logged By', default=lambda self: self.env.user)
    ticket_id = fields.Many2one('re.tenant.ticket', 'Tenant Request')
    lease_id = fields.Many2one('re.lease', compute='_compute_lease', store=True)
    execution = fields.Selection([('internal', 'Internal Technician'), ('contractor', 'External Contractor')],
                                 default='internal', required=True)
    technician_id = fields.Many2one('res.users', 'Assigned Technician', tracking=True)
    contractor_id = fields.Many2one('res.partner', 'Assigned Contractor', tracking=True,
                                    domain="[('re_is_contractor', '=', True)]")
    plan_id = fields.Many2one('re.maintenance.plan', 'Preventive Plan', readonly=True, index=True)
    scheduled_date = fields.Date('Scheduled For', readonly=True)

    # ---- Money -----------------------------------------------------------------------
    estimated_cost = fields.Monetary('Proposed Cost', tracking=True)
    approved_budget = fields.Monetary(readonly=True, tracking=True)
    pending_budget = fields.Monetary('Budget Under Approval', readonly=True)
    is_supplementary = fields.Boolean(readonly=True, copy=False)
    state_before_supplementary = fields.Char(readonly=True, copy=False)
    purchase_order_ids = fields.One2many('purchase.order', 're_work_order_id', 'Quotations / POs')
    rfq_count = fields.Integer(compute='_compute_commitments')
    selected_po_id = fields.Many2one('purchase.order', 'Selected Quotation', readonly=True, copy=False)
    vendor_bill_ids = fields.One2many('account.move', 're_work_order_id', 'Vendor Bills',
                                      domain=[('move_type', 'in', ('in_invoice', 'in_refund'))])
    committed_cost = fields.Monetary('Committed (confirmed POs not billed)', compute='_compute_commitments')
    actual_cost = fields.Monetary('Actual Expenditure', compute='_compute_costs', store=True,
                                  help='Posted vendor bills (untaxed, company currency) linked to this work order.')
    budget_variance = fields.Monetary(compute='_compute_costs', store=True)

    # ---- Dates -----------------------------------------------------------------------
    date_request = fields.Date('Request Date', default=fields.Date.context_today, required=True)
    date_start = fields.Datetime('Started', readonly=True, copy=False)
    date_target = fields.Date('Target Completion', tracking=True)
    date_done = fields.Date('Completed On', readonly=True, copy=False)
    completion_days = fields.Float(compute='_compute_kpis', store=True)
    on_time = fields.Boolean(compute='_compute_kpis', store=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue', search='_search_is_overdue')
    downtime_hours = fields.Float()
    labour_hours = fields.Float()
    pending_reason = fields.Char(tracking=True)

    # ---- Completion / feedback ---------------------------------------------------------
    completion_report = fields.Html()
    tenant_rating = fields.Selection([('1', 'Very Poor'), ('2', 'Poor'), ('3', 'Average'), ('4', 'Good'),
                                      ('5', 'Excellent')], tracking=True)
    tenant_feedback = fields.Text()
    tenant_confirmed = fields.Boolean(readonly=True, copy=False)
    is_repeat_fault = fields.Boolean(compute='_compute_kpis', store=True,
                                     help='Corrective work on the same equipment within 90 days of a previous job.')
    attachment_count = fields.Integer('Evidence Files', compute='_compute_attachment_count')

    # ---- Emergency control -------------------------------------------------------------
    is_emergency = fields.Boolean(compute='_compute_is_emergency', store=True)
    emergency_started = fields.Datetime(readonly=True, copy=False)
    emergency_review_state = fields.Selection([('none', 'N/A'), ('pending', 'Review Pending'),
                                               ('accepted', 'Accepted'), ('rejected', 'Rejected')],
                                              default='none', tracking=True, copy=False)
    emergency_reviewed_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    emergency_review_note = fields.Text(copy=False)

    _sql_constraints = [('plan_date_uniq', 'unique(plan_id, scheduled_date)',
                         'A preventive work order already exists for this plan and date.')]

    # ------------------------------------------------------------------
    @api.depends('maintenance_type')
    def _compute_is_emergency(self):
        for rec in self:
            rec.is_emergency = rec.maintenance_type == 'emergency'

    @api.depends('unit_id', 'unit_id.active_lease_id')
    def _compute_lease(self):
        for rec in self:
            rec.lease_id = rec.unit_id.active_lease_id

    @api.depends('vendor_bill_ids.state', 'vendor_bill_ids.amount_untaxed_signed', 'approved_budget')
    def _compute_costs(self):
        for rec in self:
            bills = rec.vendor_bill_ids.filtered(lambda m: m.state == 'posted')
            # amount_untaxed_signed is negative for vendor bills, positive for vendor refunds
            rec.actual_cost = -sum(bills.mapped('amount_untaxed_signed'))
            rec.budget_variance = rec.actual_cost - rec.approved_budget

    def _compute_commitments(self):
        for rec in self:
            pos = rec.purchase_order_ids.filtered(lambda p: p.state in ('purchase', 'done'))
            committed = 0.0
            for po in pos:
                for line in po.order_line:
                    remaining = line.product_qty - line.qty_invoiced
                    committed += po.currency_id._convert(remaining * line.price_unit, rec.currency_id,
                                                         rec.company_id, fields.Date.context_today(self))
            rec.committed_cost = committed
            rec.rfq_count = len(rec.purchase_order_ids)

    @api.depends('date_done', 'date_request', 'date_target', 'equipment_id', 'maintenance_type')
    def _compute_kpis(self):
        for rec in self:
            rec.completion_days = (rec.date_done - rec.date_request).days if rec.date_done and rec.date_request else 0.0
            rec.on_time = bool(rec.date_done and (not rec.date_target or rec.date_done <= rec.date_target))
            repeat = False
            if rec.equipment_id and rec.maintenance_type in ('corrective', 'emergency') and rec.date_request:
                repeat = bool(self.search_count([
                    ('id', '!=', rec._origin.id or 0), ('equipment_id', '=', rec.equipment_id.id),
                    ('maintenance_type', 'in', ('corrective', 'emergency')), ('date_done', '!=', False),
                    ('date_done', '<=', rec.date_request),
                    ('date_done', '>=', rec.date_request - timedelta(days=90))]))
            rec.is_repeat_fault = repeat

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.date_target and rec.date_target < today and rec.state not in DONE_STATES)

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [('date_target', '<', today), ('state', 'not in', DONE_STATES)]
        if (operator == '=' and value) or (operator == '!=' and not value):
            return domain
        return ['!', '&'] + domain

    def _compute_attachment_count(self):
        data = self.env['ir.attachment']._read_group([('res_model', '=', self._name), ('res_id', 'in', self.ids)],
                                                     ['res_id'], ['__count'])
        counts = dict(data)
        for rec in self:
            rec.attachment_count = counts.get(rec.id, 0)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/re/jobs/%s' % rec.id

    def _re_approval_doc_type(self):
        return 'capex' if self.expenditure_type == 'capex' else 'work_order'

    def _re_approval_amount(self):
        return self.pending_budget

    # ------------------------------------------------------------------
    @api.onchange('equipment_id')
    def _onchange_equipment(self):
        if self.equipment_id:
            self.property_id = self.equipment_id.re_property_id or self.property_id
            self.building_id = self.equipment_id.re_building_id or self.building_id
            self.floor_id = self.equipment_id.re_floor_id or self.floor_id
            self.unit_id = self.equipment_id.re_unit_id or self.unit_id

    @api.onchange('category_id')
    def _onchange_category(self):
        if self.category_id:
            self.priority = self.category_id.default_priority
            if not self.date_target:
                self.date_target = fields.Date.context_today(self) + timedelta(days=self.category_id.target_days)

    @api.constrains('estimated_cost')
    def _check_costs(self):
        for rec in self:
            if rec.estimated_cost < 0:
                raise ValidationError(_('Costs cannot be negative.'))

    @api.constrains('unit_id', 'building_id', 'property_id')
    def _check_location(self):
        for rec in self:
            if rec.unit_id and rec.unit_id.property_id != rec.property_id:
                raise ValidationError(_('The unit does not belong to the property.'))
            if rec.building_id and rec.building_id.property_id != rec.property_id:
                raise ValidationError(_('The building does not belong to the property.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.work.order') or '/'
        records = super().create(vals_list)
        for rec in records:
            if rec.technician_id:
                rec.message_subscribe(partner_ids=rec.technician_id.partner_id.ids)
        return records

    def write(self, vals):
        if 'technician_id' in vals and vals['technician_id']:
            tech = self.env['res.users'].browse(vals['technician_id'])
            for rec in self:
                rec.message_subscribe(partner_ids=tech.partner_id.ids)
        if 'estimated_cost' in vals:
            locked = self.filtered(lambda w: w.re_approval_state == 'pending')
            if locked:
                raise UserError(_('The proposed cost of %s cannot change while approval is pending.', locked[0].name))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_triage(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_('Only new requests can be triaged.'))
        self.write({'state': 'triage'})

    def action_submit_approval(self):
        for rec in self:
            if rec.state not in ('new', 'triage'):
                raise UserError(_('Work order %s is not in triage.', rec.name))
            if not rec.technician_id and not rec.contractor_id:
                raise UserError(_('Assign a technician or contractor before requesting approval.'))
            rec.write({'state': 'approval', 'pending_budget': rec.estimated_cost, 'is_supplementary': False})
            if rec._re_request_approval():
                rec._re_on_approved()

    def action_approve(self):
        self._re_approve()
        self._re_on_approved()

    def _re_on_approved(self):
        for rec in self:
            if rec.is_supplementary:
                rec.write({'approved_budget': rec.pending_budget, 'is_supplementary': False,
                           'state': rec.state_before_supplementary or 'in_progress'})
                rec.message_post(body=_('Supplementary budget approved: %s.', rec.currency_id.format(rec.approved_budget)))
            else:
                rec.write({'approved_budget': rec.pending_budget, 'state': 'assigned'})
                rec.message_post(body=_('Budget approved: %s.', rec.currency_id.format(rec.approved_budget)))

    def _re_after_reject(self):
        for rec in self:
            if rec.is_supplementary:
                rec.write({'state': rec.state_before_supplementary or 'in_progress', 'is_supplementary': False,
                           're_approval_state': 'approved', 'pending_budget': rec.approved_budget})
            else:
                rec.write({'state': 'triage'})

    def action_request_supplementary(self):
        for rec in self:
            amount = self.env.context.get('supplementary_amount') or max(rec.actual_cost, rec.estimated_cost)
            if amount <= rec.approved_budget:
                raise UserError(_('Set the proposed cost above the approved budget to request a supplementary approval.'))
            rec.write({'is_supplementary': True, 'state_before_supplementary': rec.state, 'pending_budget': amount,
                       'state': 'approval'})
            if rec._re_request_approval():
                rec._re_on_approved()

    def action_emergency_start(self):
        """Controlled emergency: work may start before approval; a manager must
        review it afterwards (tracked by the 'emergency_not_reviewed' control)."""
        for rec in self:
            if rec.state not in ('new', 'triage', 'approval'):
                raise UserError(_('Emergency start is only possible before work begins.'))
            if not rec.technician_id and not rec.contractor_id:
                raise UserError(_('Assign a technician or contractor.'))
            rec.write({'maintenance_type': 'emergency', 'state': 'in_progress', 'date_start': fields.Datetime.now(),
                       'emergency_started': fields.Datetime.now(), 'emergency_review_state': 'pending',
                       'approved_budget': rec.estimated_cost, 'pending_budget': rec.estimated_cost,
                       're_requested_by_id': self.env.uid, 're_requested_date': fields.Datetime.now()})
            rec._re_log('override', rec.estimated_cost, _('Emergency work started before approval (provisional budget).'))
            managers = self.env.ref('real_estate_lifecycle.group_re_maintenance_manager').users.filtered(
                lambda u: rec.company_id in u.company_ids and u != self.env.user)
            for user in managers[:3]:
                rec.activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                                      summary=_('Review emergency work %s', rec.name))

    def action_emergency_review(self):
        if not self.env.user.has_group('real_estate_lifecycle.group_re_maintenance_manager'):
            raise UserError(_('Only maintenance managers or above can review emergency work.'))
        decision = self.env.context.get('review_decision', 'accepted')
        for rec in self:
            if rec.emergency_review_state != 'pending':
                raise UserError(_('No emergency review pending.'))
            if rec.re_requested_by_id == self.env.user:
                raise UserError(_('Segregation of duties: the person who started the emergency cannot review it.'))
            vals = {'emergency_review_state': decision, 'emergency_reviewed_by_id': self.env.uid}
            if decision == 'accepted':
                vals.update({'re_approval_state': 'approved', 're_approved_by_id': self.env.uid,
                             're_approved_date': fields.Datetime.now()})
            rec.write(vals)
            rec._re_log('approved' if decision == 'accepted' else 'rejected', rec.approved_budget,
                        _('Emergency review: %s', decision))
            rec.activity_ids.action_feedback(feedback=_('Emergency reviewed: %s', decision))

    def action_start(self):
        for rec in self:
            if rec.state != 'assigned':
                raise UserError(_('Work order %s must be approved and assigned first.', rec.name))
        self.write({'state': 'in_progress', 'date_start': fields.Datetime.now()})

    def action_set_pending(self):
        for rec in self:
            if not rec.pending_reason:
                raise UserError(_('Enter the pending reason (parts, contractor, access...).'))
        self.write({'state': 'pending'})

    def action_resume(self):
        self.write({'state': 'in_progress', 'pending_reason': False})

    def action_complete(self):
        for rec in self:
            if rec.state not in ('in_progress', 'pending'):
                raise UserError(_('Only work in progress can be completed.'))
            if not rec.completion_report or rec.completion_report in ('<p><br></p>', '<p></p>'):
                raise UserError(_('Write the completion report for %s.', rec.name))
            tol = rec.company_id.re_wo_tolerance_pct / 100.0
            if rec.actual_cost > rec.approved_budget * (1 + tol) + 0.005:
                raise UserError(_('Actual expenditure %(a)s exceeds the approved budget %(b)s. Request a supplementary '
                                  'approval before completing.', a=rec.currency_id.format(rec.actual_cost),
                                  b=rec.currency_id.format(rec.approved_budget)))
            rec.write({'state': 'completed', 'date_done': fields.Date.context_today(self)})
            if rec.equipment_id and rec.maintenance_type in ('corrective', 'emergency', 'preventive'):
                rec.equipment_id.sudo().message_post(body=_('Work order %(wo)s completed: %(t)s (cost %(c)s).', wo=rec.name,
                                                     t=rec.title, c=rec.currency_id.format(rec.actual_cost)))
            if rec.ticket_id and rec.ticket_id.state not in ('resolved', 'closed'):
                rec.ticket_id.sudo().write({'state': 'resolved', 'resolution': _('Work order %s completed.', rec.name),
                                     'date_resolved': fields.Datetime.now()})

    def action_request_confirmation(self):
        for rec in self:
            if rec.state != 'completed':
                raise UserError(_('Complete the work order first.'))
            if rec.requested_by_partner_id:
                rec.state = 'tenant_confirmation'
                rec.message_post(body=_('The work on "%s" is complete. Please confirm and rate the service in your '
                                        'portal.', rec.title), partner_ids=rec.requested_by_partner_id.ids,
                                 message_type='comment', subtype_xmlid='mail.mt_comment')
            else:
                rec.action_close()

    def action_tenant_confirm(self, rating=None, feedback=None):
        for rec in self:
            if rec.state not in ('completed', 'tenant_confirmation'):
                raise UserError(_('Nothing to confirm.'))
            rec.write({'tenant_confirmed': True, 'tenant_rating': rating or rec.tenant_rating,
                       'tenant_feedback': feedback or rec.tenant_feedback, 'state': 'closed'})

    def action_close(self):
        for rec in self:
            if rec.state not in ('completed', 'tenant_confirmation'):
                raise UserError(_('Only completed work orders can be closed.'))
            if rec.state == 'tenant_confirmation' and not rec.tenant_confirmed:
                rec.message_post(body=_('Closed by %s without tenant confirmation.', self.env.user.name))
        self.write({'state': 'closed'})

    def action_cancel(self):
        for rec in self:
            if rec.vendor_bill_ids.filtered(lambda m: m.state == 'posted'):
                raise UserError(_('Work order %s has posted bills and cannot be cancelled.', rec.name))
            rec.purchase_order_ids.filtered(lambda p: p.state in ('draft', 'sent', 'to approve')).button_cancel()
        self.write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # Procurement
    # ------------------------------------------------------------------
    def _re_product(self):
        self.ensure_one()
        return self.company_id._re_get_product('capex' if self.expenditure_type == 'capex' else 'maintenance')

    def action_open_rfq_wizard(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Request Quotations'), 'res_model': 're.rfq.wizard',
                'view_mode': 'form', 'target': 'new', 'context': {'default_work_order_id': self.id}}

    def _re_select_quotation(self, po):
        self.ensure_one()
        if self.re_approval_state == 'pending':
            raise UserError(_('Approval is already pending.'))
        amount = po.currency_id._convert(po.amount_untaxed, self.currency_id, self.company_id,
                                         fields.Date.context_today(self))
        self.write({'selected_po_id': po.id, 'contractor_id': po.partner_id.id, 'execution': 'contractor',
                    'estimated_cost': amount})
        self.message_post(body=_('Quotation %(po)s from %(v)s selected (%(amt)s). Other quotations: %(others)s',
                                 po=po.name, v=po.partner_id.name, amt=self.currency_id.format(amount),
                                 others=', '.join('%s: %s' % (o.partner_id.name, o.currency_id.format(o.amount_untaxed))
                                                  for o in self.purchase_order_ids - po) or '-'))

    def action_confirm_selected_po(self):
        for rec in self:
            po = rec.selected_po_id
            if not po:
                raise UserError(_('Select a quotation first.'))
            if not rec._re_is_approved():
                raise UserError(_('The work order budget must be approved before confirming the purchase order.'))
            po.button_confirm()
            (rec.purchase_order_ids - po).filtered(lambda p: p.state in ('draft', 'sent')).button_cancel()
            if rec.state == 'approval':
                rec.state = 'assigned'

    def action_create_vendor_bill(self):
        """Direct contractor bill without PO (flagged by controls when POs are required)."""
        self.ensure_one()
        if not self.contractor_id:
            raise UserError(_('Set the contractor first.'))
        if not self._re_is_approved() and not self.is_emergency:
            raise UserError(_('Expenditure requires an approved budget (or an emergency start).'))
        product = self._re_product()
        billed = self.actual_cost
        bill = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'in_invoice', 'partner_id': self.contractor_id.id,
            'invoice_date': fields.Date.context_today(self), 're_work_order_id': self.id,
            'invoice_origin': self.name, 'ref': False,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id, 'name': '%s - %s' % (self.name, self.title), 'quantity': 1,
                'price_unit': max(self.approved_budget - billed, 0.0),
                'analytic_distribution': self.property_id._re_analytic_distribution(self.building_id)})],
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': bill.id, 'view_mode': 'form'}

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Quotation Comparison'), 'res_model': 'purchase.order',
                'view_mode': 'list,form', 'domain': [('re_work_order_id', '=', self.id)],
                'views': [(self.env.ref('real_estate_lifecycle.view_re_po_comparison_list').id, 'list'), (False, 'form')],
                'context': {'default_re_work_order_id': self.id}}

    def action_view_bills(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_in_invoice_type')
        action['domain'] = [('re_work_order_id', '=', self.id)]
        action['context'] = {'default_move_type': 'in_invoice', 'default_re_work_order_id': self.id}
        return action

    def action_view_attachments(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Evidence'), 'res_model': 'ir.attachment',
                'view_mode': 'kanban,list,form', 'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
                'context': {'default_res_model': self._name, 'default_res_id': self.id}}
