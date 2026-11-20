# -*- coding: utf-8 -*-
"""Tenant and contractor self-service portal.

Reads are performed with the portal user's own environment, so the portal record
rules (security/re_rules.xml) restrict every record to the logged-in tenant or
contractor. Writes go through explicit, validated actions executed with sudo only
after the record has been read successfully as the portal user."""
import base64

from markupsafe import Markup

from odoo import fields, http, _
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

MAX_UPLOAD = 10 * 1024 * 1024


class RePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        env = request.env
        if 're_lease_count' in counters:
            values['re_lease_count'] = env['re.lease'].search_count([]) if env['re.lease'].has_access('read') else 0
        if 're_request_count' in counters:
            values['re_request_count'] = env['re.tenant.ticket'].search_count([]) \
                if env['re.tenant.ticket'].has_access('read') else 0
        if 're_job_count' in counters:
            partner = env.user.partner_id.commercial_partner_id
            values['re_job_count'] = env['re.work.order'].search_count(
                [('contractor_id', 'child_of', partner.id)]) if env['re.work.order'].has_access('read') else 0
        return values

    def _re_document(self, model, record_id):
        try:
            record = request.env[model].browse(int(record_id)).exists()
            if not record:
                raise MissingError(_('Not found'))
            record.check_access('read')
            return record
        except (AccessError, MissingError, ValueError):
            return None

    def _re_attach(self, record, files):
        for f in files or []:
            if not f or not getattr(f, 'filename', None):
                continue
            content = f.read()
            if len(content) > MAX_UPLOAD:
                raise UserError(_('File %s is larger than 10 MB.', f.filename))
            request.env['ir.attachment'].sudo().create({
                'name': f.filename, 'datas': base64.b64encode(content), 'res_model': record._name,
                'res_id': record.id, 'mimetype': f.mimetype,
            })

    # ------------------------------------------------------------------ leases
    @http.route(['/my/leases'], type='http', auth='user', website=True)
    def portal_my_leases(self, **kw):
        leases = request.env['re.lease'].search([], order='date_start desc')
        return request.render('real_estate_lifecycle.portal_my_leases', {
            'leases': leases, 'page_name': 're_leases'})

    @http.route(['/my/leases/<int:lease_id>'], type='http', auth='user', website=True)
    def portal_my_lease(self, lease_id, **kw):
        lease = self._re_document('re.lease', lease_id)
        if not lease:
            return request.redirect('/my')
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 're.lease'), ('res_id', '=', lease.id), ('id', '=', lease.sudo().signed_attachment_id.id)])
        return request.render('real_estate_lifecycle.portal_my_lease', {
            'lease': lease.sudo(), 'attachments': attachments, 'page_name': 're_lease',
            'success': kw.get('success')})

    @http.route(['/my/leases/<int:lease_id>/renewal'], type='http', auth='user', website=True, methods=['POST'])
    def portal_lease_renewal(self, lease_id, **post):
        lease = self._re_document('re.lease', lease_id)
        if not lease:
            return request.redirect('/my')
        request.env['re.tenant.ticket'].sudo().create({
            'subject': _('Renewal request for %s', lease.name), 'ticket_type': 'renewal_request',
            'partner_id': request.env.user.partner_id.commercial_partner_id.id, 'lease_id': lease.id,
            'description': post.get('message') or '', 'source': 'portal'})
        return request.redirect('/my/leases/%s?success=renewal' % lease.id)

    # ------------------------------------------------------------------ statement
    @http.route(['/my/re/statement'], type='http', auth='user', website=True)
    def portal_statement(self, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        if not partner.sudo().re_is_tenant:
            return request.redirect('/my')
        data = partner.sudo()._re_statement_data()
        return request.render('real_estate_lifecycle.portal_statement', {
            'partner': partner, 'data': data, 'currency': request.env.company.currency_id,
            'page_name': 're_statement'})

    @http.route(['/my/re/statement/pdf'], type='http', auth='user', website=True)
    def portal_statement_pdf(self, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        if not partner.sudo().re_is_tenant:
            return request.redirect('/my')
        pdf, _ftype = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'real_estate_lifecycle.action_report_tenant_statement', [partner.id])
        return request.make_response(pdf, headers=[('Content-Type', 'application/pdf'),
                                                   ('Content-Disposition', 'attachment; filename="statement.pdf"')])

    # ------------------------------------------------------------------ requests
    @http.route(['/my/re/requests'], type='http', auth='user', website=True)
    def portal_requests(self, **kw):
        tickets = request.env['re.tenant.ticket'].search([])
        wos = request.env['re.work.order'].search([('requested_by_partner_id', 'child_of',
                                                    request.env.user.partner_id.commercial_partner_id.id)])
        announcements = request.env['re.announcement'].search([])
        return request.render('real_estate_lifecycle.portal_requests', {
            'tickets': tickets, 'work_orders': wos, 'announcements': announcements, 'page_name': 're_requests',
            'success': kw.get('success')})

    @http.route(['/my/re/requests/new'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_request_new(self, **post):
        partner = request.env.user.partner_id.commercial_partner_id
        leases = request.env['re.lease'].search([('state', 'in', ('active', 'expiring'))])
        if request.httprequest.method == 'GET':
            invoices = request.env['account.move'].search([('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
                                                          limit=50)
            return request.render('real_estate_lifecycle.portal_request_form', {
                'leases': leases, 'invoices': invoices, 'page_name': 're_request_new',
                'categories': request.env['re.complaint.category'].sudo().search([])})
        lease = self._re_document('re.lease', post.get('lease_id') or 0)
        if not lease:
            return request.redirect('/my/re/requests')
        lease = lease.sudo()  # access verified above as the portal user
        kind = post.get('request_type')
        subject = (post.get('subject') or '').strip()[:200] or _('Request')
        description = (post.get('description') or '').strip()
        category = request.env['re.complaint.category'].sudo().browse(int(post.get('category_id') or 0)).exists()
        if kind == 'maintenance':
            record = request.env['re.work.order'].sudo().create({
                'title': subject, 'property_id': lease.property_id.id,
                'building_id': (lease.building_id or lease.unit_ids[:1].building_id).id,
                'unit_id': lease.unit_ids[:1].id, 'description': description, 'requested_by_partner_id': partner.id,
                'maintenance_type': 'corrective', 'category_id': category.maintenance_category_id.id,
                'requested_by_user_id': request.env.ref('base.user_root').id})
        else:
            vals = {'subject': subject, 'partner_id': partner.id, 'lease_id': lease.id, 'description': description,
                    'source': 'portal', 'category_id': category.id,
                    'ticket_type': kind if kind in ('complaint', 'billing_dispute', 'renewal_request', 'document',
                                                    'enquiry', 'feedback') else 'enquiry'}
            if kind == 'billing_dispute' and post.get('invoice_id'):
                invoice = self._re_document('account.move', post.get('invoice_id'))
                if invoice and invoice.move_type == 'out_invoice':
                    vals['invoice_id'] = invoice.id
            record = request.env['re.tenant.ticket'].sudo().create(vals)
        self._re_attach(record, request.httprequest.files.getlist('attachments'))
        return request.redirect('/my/re/requests?success=%s' % record.name)

    @http.route(['/my/re/requests/<int:ticket_id>'], type='http', auth='user', website=True)
    def portal_request(self, ticket_id, **kw):
        ticket = self._re_document('re.tenant.ticket', ticket_id)
        if not ticket:
            return request.redirect('/my/re/requests')
        return request.render('real_estate_lifecycle.portal_request', {'ticket': ticket.sudo(),
                                                                       'page_name': 're_request'})

    @http.route(['/my/re/wo/<int:wo_id>/confirm'], type='http', auth='user', website=True, methods=['POST'])
    def portal_wo_confirm(self, wo_id, **post):
        wo = self._re_document('re.work.order', wo_id)
        partner = request.env.user.partner_id.commercial_partner_id
        if not wo or wo.sudo().requested_by_partner_id.commercial_partner_id != partner:
            return request.redirect('/my/re/requests')
        rating = post.get('rating') if post.get('rating') in ('1', '2', '3', '4', '5') else None
        wo.sudo().action_tenant_confirm(rating=rating, feedback=(post.get('feedback') or '')[:2000])
        return request.redirect('/my/re/requests?success=%s' % wo.name)

    # ------------------------------------------------------------------ contractor jobs
    @http.route(['/my/re/jobs'], type='http', auth='user', website=True)
    def portal_jobs(self, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        jobs = request.env['re.work.order'].search([('contractor_id', 'child_of', partner.id)])
        return request.render('real_estate_lifecycle.portal_jobs', {'jobs': jobs, 'page_name': 're_jobs'})

    @http.route(['/my/re/jobs/<int:wo_id>'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_job(self, wo_id, **post):
        wo = self._re_document('re.work.order', wo_id)
        partner = request.env.user.partner_id.commercial_partner_id
        if not wo or wo.sudo().contractor_id.commercial_partner_id != partner:
            return request.redirect('/my/re/jobs')
        error = None
        if request.httprequest.method == 'POST':
            sudo_wo = wo.sudo()
            try:
                action = post.get('action')
                if post.get('report'):
                    sudo_wo.completion_report = Markup(sudo_wo.completion_report or '') + \
                        Markup('<p>%s</p>') % post['report'][:5000]
                self._re_attach(sudo_wo, request.httprequest.files.getlist('attachments'))
                if action == 'start':
                    sudo_wo.action_start()
                elif action == 'complete':
                    sudo_wo.action_complete()
                sudo_wo.message_post(body=_('Update from contractor %s via portal.', partner.name))
            except UserError as e:
                error = str(e)
        return request.render('real_estate_lifecycle.portal_job', {'wo': wo.sudo(), 'page_name': 're_job',
                                                                   'error': error})
