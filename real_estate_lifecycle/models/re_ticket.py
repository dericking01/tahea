# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReTenantTicket(models.Model):
    """Tenant complaints, billing disputes, renewal requests, document submissions
    and general enquiries (portal or back-office)."""
    _name = 're.tenant.ticket'
    _description = 'Tenant Request / Complaint'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    subject = fields.Char(required=True, tracking=True)
    ticket_type = fields.Selection([
        ('complaint', 'Complaint'),
        ('billing_dispute', 'Billing Dispute'),
        ('renewal_request', 'Lease Renewal Request'),
        ('document', 'Document Submission'),
        ('enquiry', 'General Enquiry'),
        ('feedback', 'Feedback'),
    ], required=True, default='complaint', tracking=True)
    category_id = fields.Many2one('re.complaint.category', tracking=True)
    partner_id = fields.Many2one('res.partner', 'Tenant', required=True, index=True)
    lease_id = fields.Many2one('re.lease', domain="[('tenant_id', '=', partner_id)]")
    property_id = fields.Many2one('re.property', compute='_compute_location', store=True, readonly=False, index=True,
                                  precompute=True)
    building_id = fields.Many2one('re.building', compute='_compute_location', store=True, readonly=False,
                                  precompute=True)
    unit_id = fields.Many2one('re.unit', compute='_compute_location', store=True, readonly=False, precompute=True)
    company_id = fields.Many2one('res.company', compute='_compute_location', store=True, readonly=False,
                                 precompute=True)
    manager_id = fields.Many2one(related='property_id.manager_id', store=True)
    description = fields.Html()
    priority = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent')], default='1')
    state = fields.Selection([
        ('new', 'New'), ('in_progress', 'In Progress'), ('waiting', 'Waiting on Tenant'),
        ('resolved', 'Resolved'), ('closed', 'Closed'), ('rejected', 'Rejected')], default='new', tracking=True)
    user_id = fields.Many2one('res.users', 'Assigned To', tracking=True)
    invoice_id = fields.Many2one('account.move', 'Disputed Invoice', domain="[('partner_id', 'child_of', partner_id)]")
    work_order_id = fields.Many2one('re.work.order', copy=False)
    building_issue_id = fields.Many2one('re.building.issue', 'Shared Building Issue', copy=False, tracking=True)
    satisfaction = fields.Selection([('1', 'Very Dissatisfied'), ('2', 'Dissatisfied'), ('3', 'Neutral'),
                                     ('4', 'Satisfied'), ('5', 'Very Satisfied')])
    feedback = fields.Text()
    resolution = fields.Text(tracking=True)
    date_resolved = fields.Datetime(readonly=True)
    source = fields.Selection([('portal', 'Tenant Portal'), ('phone', 'Phone'), ('email', 'Email'),
                               ('walk_in', 'Walk-in'), ('staff', 'Staff')], default='staff')

    @api.depends('lease_id')
    def _compute_location(self):
        for rec in self:
            if rec.lease_id:
                rec.property_id = rec.lease_id.property_id
                rec.building_id = rec.lease_id.building_id or rec.lease_id.unit_ids[:1].building_id
                rec.unit_id = rec.lease_id.unit_ids[:1]
                rec.company_id = rec.lease_id.company_id
            else:
                rec.property_id = rec.property_id
                rec.building_id = rec.building_id
                rec.unit_id = rec.unit_id
                rec.company_id = rec.company_id or self.env.company

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/re/requests/%s' % rec.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('re.tenant.ticket') or '/'
        records = super().create(vals_list)
        for rec in records:
            if rec.ticket_type == 'billing_dispute' and rec.invoice_id:
                rec.invoice_id.sudo().write({'re_dispute_state': 'open', 're_dispute_reason': rec.subject,
                                             're_dispute_ticket_id': rec.id})
            if not rec.user_id and rec.property_id.manager_id:
                rec.user_id = rec.property_id.manager_id
            rec._re_cluster()
        return records

    def _re_cluster(self):
        """Group complaints of the same category in the same building into a
        shared building issue, so systemic problems are visible to management."""
        for rec in self:
            if rec.ticket_type != 'complaint' or not rec.category_id.is_building_wide or not rec.building_id:
                continue
            Issue = self.env['re.building.issue'].sudo()
            issue = Issue.search([('building_id', '=', rec.building_id.id), ('category_id', '=', rec.category_id.id),
                                  ('state', '=', 'open')], limit=1)
            if issue:
                rec.sudo().building_issue_id = issue
                issue.message_post(body=_('New related complaint %(t)s from %(p)s.', t=rec.name, p=rec.partner_id.name))
                continue
            company = rec.company_id or self.env.company
            since = fields.Datetime.now() - timedelta(days=company.re_cluster_window_days or 14)
            similar = self.sudo().search([
                ('building_id', '=', rec.building_id.id), ('category_id', '=', rec.category_id.id),
                ('ticket_type', '=', 'complaint'), ('state', 'not in', ('closed', 'rejected', 'resolved')),
                ('create_date', '>=', since), ('building_issue_id', '=', False)])
            if len(similar.mapped('partner_id')) >= (company.re_cluster_threshold or 2):
                issue = Issue.create({
                    'name': _('%(cat)s - %(bld)s', cat=rec.category_id.name, bld=rec.building_id.display_name),
                    'building_id': rec.building_id.id, 'category_id': rec.category_id.id,
                    'user_id': rec.building_id.manager_id.id,
                })
                similar.write({'building_issue_id': issue.id})
                issue.message_post(body=_('Shared issue detected: %(n)s tenants reported "%(cat)s" within %(d)s days.',
                                          n=len(similar.mapped('partner_id')), cat=rec.category_id.name,
                                          d=company.re_cluster_window_days))
                if issue.user_id:
                    issue.activity_schedule('mail.mail_activity_data_todo', user_id=issue.user_id.id,
                                            summary=_('Shared building issue: %s', issue.name))

    def action_start(self):
        self.write({'state': 'in_progress', 'user_id': self.user_id.id or self.env.uid})

    def action_resolve(self):
        for rec in self:
            if not rec.resolution:
                raise UserError(_('Describe the resolution for %s.', rec.name))
            if rec.ticket_type == 'billing_dispute' and rec.invoice_id.re_dispute_state == 'open':
                rec.invoice_id.sudo().re_dispute_state = 'resolved'
        self.write({'state': 'resolved', 'date_resolved': fields.Datetime.now()})

    def action_reject(self):
        for rec in self:
            if not rec.resolution:
                raise UserError(_('Explain why %s is rejected.', rec.name))
            if rec.ticket_type == 'billing_dispute' and rec.invoice_id.re_dispute_state == 'open':
                rec.invoice_id.sudo().re_dispute_state = 'rejected'
        self.write({'state': 'rejected', 'date_resolved': fields.Datetime.now()})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_create_work_order(self):
        self.ensure_one()
        if self.work_order_id:
            raise UserError(_('A work order already exists.'))
        if not self.property_id:
            raise UserError(_('Set the property first.'))
        wo = self.env['re.work.order'].create({
            'title': self.subject, 'property_id': self.property_id.id, 'building_id': self.building_id.id,
            'unit_id': self.unit_id.id, 'description': self.description, 'requested_by_partner_id': self.partner_id.id,
            'ticket_id': self.id, 'maintenance_type': 'corrective', 'priority': self.priority,
            'category_id': self.category_id.maintenance_category_id.id,
        })
        self.write({'work_order_id': wo.id, 'state': 'in_progress'})
        return {'type': 'ir.actions.act_window', 'res_model': 're.work.order', 'res_id': wo.id, 'view_mode': 'form'}

    def action_create_renewal(self):
        self.ensure_one()
        if self.ticket_type != 'renewal_request' or not self.lease_id:
            raise UserError(_('Only renewal requests linked to a lease can be converted.'))
        self.state = 'in_progress'
        return self.lease_id.action_open_renew_wizard()


class ReBuildingIssue(models.Model):
    _name = 're.building.issue'
    _description = 'Shared Building Issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, id desc'

    name = fields.Char(required=True)
    building_id = fields.Many2one('re.building', required=True, index=True)
    property_id = fields.Many2one(related='building_id.property_id', store=True)
    company_id = fields.Many2one(related='building_id.company_id', store=True)
    category_id = fields.Many2one('re.complaint.category', required=True)
    state = fields.Selection([('open', 'Open'), ('resolved', 'Resolved')], default='open', tracking=True)
    user_id = fields.Many2one('res.users', 'Responsible')
    ticket_ids = fields.One2many('re.tenant.ticket', 'building_issue_id')
    ticket_count = fields.Integer(compute='_compute_counts', store=True)
    tenant_count = fields.Integer(compute='_compute_counts', store=True)
    work_order_id = fields.Many2one('re.work.order')
    root_cause = fields.Text()
    resolution = fields.Text()

    @api.depends('ticket_ids', 'ticket_ids.partner_id')
    def _compute_counts(self):
        for rec in self:
            rec.ticket_count = len(rec.ticket_ids)
            rec.tenant_count = len(rec.ticket_ids.mapped('partner_id'))

    def action_create_work_order(self):
        self.ensure_one()
        if not self.work_order_id:
            self.work_order_id = self.env['re.work.order'].create({
                'title': self.name, 'property_id': self.property_id.id, 'building_id': self.building_id.id,
                'maintenance_type': 'corrective', 'priority': '2',
                'category_id': self.category_id.maintenance_category_id.id,
                'description': _('Shared building issue affecting %s tenants.', self.tenant_count)})
        return {'type': 'ir.actions.act_window', 'res_model': 're.work.order', 'res_id': self.work_order_id.id,
                'view_mode': 'form'}

    def action_resolve(self):
        for rec in self:
            if not rec.resolution:
                raise UserError(_('Describe the resolution.'))
            open_tickets = rec.ticket_ids.filtered(lambda t: t.state not in ('resolved', 'closed', 'rejected'))
            open_tickets.write({'state': 'resolved', 'resolution': rec.resolution,
                                'date_resolved': fields.Datetime.now()})
            for t in open_tickets:
                t.message_post(body=_('Resolved as part of shared building issue %(i)s: %(r)s', i=rec.name,
                                      r=rec.resolution), message_type='comment', subtype_xmlid='mail.mt_comment',
                               partner_ids=t.partner_id.ids)
        self.write({'state': 'resolved'})


class ReAnnouncement(models.Model):
    _name = 're.announcement'
    _description = 'Tenant Announcement'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char('Title', required=True)
    body = fields.Html(required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    date_expiry = fields.Date('Visible Until')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    property_ids = fields.Many2many('re.property', string='Properties',
                                    help='Leave empty to address all properties of the company.')
    building_ids = fields.Many2many('re.building', string='Buildings')
    published = fields.Boolean(default=False, tracking=True)

    def _target_leases(self):
        self.ensure_one()
        domain = [('state', 'in', ('active', 'expiring')), ('company_id', '=', self.company_id.id)]
        if self.property_ids:
            domain.append(('property_id', 'in', self.property_ids.ids))
        if self.building_ids:
            domain.append(('building_id', 'in', self.building_ids.ids))
        return self.env['re.lease'].sudo().search(domain)

    def action_publish(self):
        self.write({'published': True})

    def action_send_email(self):
        for rec in self:
            partners = rec._target_leases().mapped('tenant_id')
            if not partners:
                raise UserError(_('No tenants with active leases match this announcement.'))
            rec.published = True
            rec.message_post(body=rec.body, subject=rec.name, partner_ids=partners.ids,
                             message_type='comment', subtype_xmlid='mail.mt_comment')
