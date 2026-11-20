# -*- coding: utf-8 -*-
from odoo import http
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install', 're_lpm')
class TestPortalHttp(HttpCase):
    """Tenant & contractor self-service over HTTP, as real portal users."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        company = env.company
        company._re_set_default_products()
        ptype = env.ref('real_estate_lifecycle.property_type_apartment')
        cls.prop = env['re.property'].create({'name': 'Portal Towers', 'code': 'PTW', 'property_type_id': ptype.id,
                                              'company_id': company.id})
        cls.unit = env['re.unit'].create({'name': 'P1', 'property_id': cls.prop.id, 'unit_type': 'apartment',
                                          'area': 70, 'market_rent': 1_000_000})
        cls.tenant = env['res.partner'].create({'name': 'Portal Tenant', 'email': 'pt@example.com'})
        cls.tenant_user = new_test_user(env, login='portal_tenant', password='portal_tenant_pw',
                                        groups='base.group_portal', partner_id=cls.tenant.id)
        lease = env['re.lease'].create({
            'tenant_id': cls.tenant.id, 'property_id': cls.prop.id, 'unit_ids': [(6, 0, cls.unit.ids)],
            'lease_type_id': env.ref('real_estate_lifecycle.lease_type_residential').id,
            'date_start': '2026-01-01', 'date_end': '2027-12-31', 'rent_amount': 1_000_000})
        lease.write({'state': 'approved', 're_approval_state': 'not_required'})
        lease.action_activate()
        cls.lease = lease
        cls.contractor = env['res.partner'].create({'name': 'Portal Contractor', 're_is_contractor': True,
                                                    'is_company': True, 'email': 'pc@example.com'})
        cls.contractor_user = new_test_user(env, login='portal_contractor', password='portal_contractor_pw',
                                            groups='base.group_portal', partner_id=cls.contractor.id)
        cls.job = env['re.work.order'].create({
            'title': 'Fix gate', 'property_id': cls.prop.id, 'contractor_id': cls.contractor.id,
            'execution': 'contractor', 'state': 'assigned', 're_approval_state': 'not_required'})

    def test_01_tenant_portal(self):
        self.authenticate('portal_tenant', 'portal_tenant_pw')
        for url in ('/my', '/my/leases', '/my/leases/%s' % self.lease.id, '/my/re/requests',
                    '/my/re/requests/new', '/my/re/statement'):
            res = self.url_open(url)
            self.assertEqual(res.status_code, 200, url)
        self.assertIn(self.lease.name, self.url_open('/my/leases').text)
        res = self.url_open('/my/re/requests/new', data={
            'csrf_token': http.Request.csrf_token(self), 'lease_id': self.lease.id, 'request_type': 'maintenance',
            'subject': 'Leaking tap', 'description': 'Kitchen tap leaking'})
        self.assertEqual(res.status_code, 200)
        wo = self.env['re.work.order'].search([('title', '=', 'Leaking tap')])
        self.assertEqual(wo.requested_by_partner_id, self.tenant)
        self.assertEqual(wo.unit_id, self.unit)
        self.url_open('/my/re/requests/new', data={
            'csrf_token': http.Request.csrf_token(self), 'lease_id': self.lease.id, 'request_type': 'complaint',
            'subject': 'No water', 'description': 'Since morning',
            'category_id': self.env.ref('real_estate_lifecycle.complaint_category_water').id})
        ticket = self.env['re.tenant.ticket'].search([('subject', '=', 'No water')])
        self.assertEqual(ticket.partner_id, self.tenant)
        self.assertEqual(ticket.source, 'portal')
        # another tenant's lease is not reachable
        other = self.lease.copy({'tenant_id': self.env['res.partner'].create({'name': 'X'}).id})
        res = self.url_open('/my/leases/%s' % other.id)
        self.assertNotIn(other.name, res.text)

    def test_02_contractor_portal(self):
        self.authenticate('portal_contractor', 'portal_contractor_pw')
        res = self.url_open('/my/re/jobs')
        self.assertIn(self.job.name, res.text)
        self.url_open('/my/re/jobs/%s' % self.job.id, data={
            'csrf_token': http.Request.csrf_token(self), 'action': 'start', 'report': 'On site <b>now</b>'})
        self.assertEqual(self.job.state, 'in_progress')
        self.url_open('/my/re/jobs/%s' % self.job.id, data={
            'csrf_token': http.Request.csrf_token(self), 'action': 'complete', 'report': 'Gate motor replaced'})
        self.assertEqual(self.job.state, 'completed')
        self.assertIn('&lt;b&gt;', self.job.completion_report, 'contractor input is escaped')

    def test_03_backend_assets_compile(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_backend', css=True, js=True)
        css = bundle.css()
        js = bundle.js()
        self.assertTrue(css and js)
        self.assertIn(b're_portfolio_dashboard', js.raw)
        self.assertIn(b'o_re_card', css.raw)
