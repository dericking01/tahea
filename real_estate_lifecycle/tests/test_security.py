# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestSecurity(ReCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_manager = new_test_user(cls.env, login='re_pm2', groups='real_estate_lifecycle.group_re_property_manager',
                                          company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.property2 = cls.env['re.property'].create({
            'name': 'Mikocheni Plaza', 'code': 'MKP', 'property_type_id': cls.ptype.id, 'company_id': cls.company.id,
            'manager_id': cls.other_manager.id, 'investor_user_ids': [(6, 0, cls.investor.ids)]})
        cls.unit2 = cls.env['re.unit'].create({'name': 'P-1', 'property_id': cls.property2.id, 'unit_type': 'retail',
                                               'area': 40})
        cls.lease1 = cls._activate(cls._make_lease())
        cls.other_tenant = cls.env['res.partner'].create({'name': 'Second Tenant'})
        lease2 = cls.env['re.lease'].create({
            'tenant_id': cls.other_tenant.id, 'property_id': cls.property2.id, 'unit_ids': [(6, 0, cls.unit2.ids)],
            'lease_type_id': cls.lease_type.id, 'date_start': '2026-01-01', 'date_end': '2027-12-31',
            'rent_amount': 900_000})
        lease2.with_user(cls.other_manager).action_submit()
        lease2.with_user(cls.approver).action_approve()
        lease2.action_activate()
        cls.lease2 = lease2

    def test_01_multi_company(self):
        """Test 10: a user of company A cannot access company B records."""
        company_b = self.env['res.company'].create({'name': 'RE Company B'})
        prop_b = self.env['re.property'].create({
            'name': 'Arusha Mall', 'code': 'ARM', 'property_type_id': self.ptype.id, 'company_id': company_b.id})
        user_a = self.accountant
        props = self.env['re.property'].with_user(user_a).search([])
        self.assertIn(self.property, props)
        self.assertNotIn(prop_b, props)
        with self.assertRaises(AccessError):
            prop_b.with_user(user_a).read(['name'])
        data = self.env['re.analytics'].with_user(user_a).get_dashboard_data({})
        self.assertNotIn(prop_b.id, data['property_ids'])

    def test_02_property_manager_scope(self):
        props = self.env['re.property'].with_user(self.pm).search([])
        self.assertIn(self.property, props)
        self.assertNotIn(self.property2, props, 'property managers only see authorised properties')
        leases = self.env['re.lease'].with_user(self.pm).search([])
        self.assertIn(self.lease1, leases)
        self.assertNotIn(self.lease2, leases)
        with self.assertRaises(AccessError):
            self.lease2.with_user(self.pm).read(['rent_amount'])
        # granting authorisation opens access
        self.property2.user_ids = [(4, self.pm.id)]
        self.assertIn(self.property2, self.env['re.property'].with_user(self.pm).search([]))

    def test_03_technician(self):
        wo_mine = self.env['re.work.order'].create({'title': 'Mine', 'property_id': self.property.id,
                                                    'technician_id': self.technician.id})
        wo_other = self.env['re.work.order'].create({'title': 'Other', 'property_id': self.property2.id})
        visible = self.env['re.work.order'].with_user(self.technician).search([])
        self.assertIn(wo_mine, visible)
        self.assertNotIn(wo_other, visible)
        with self.assertRaises(AccessError):
            wo_other.with_user(self.technician).write({'title': 'hack'})
        with self.assertRaises(AccessError):
            self.env['re.work.order'].with_user(self.technician).create({'title': 'x', 'property_id': self.property.id})
        with self.assertRaises(AccessError):
            self.env['re.security.deposit'].with_user(self.technician).search([])

    def test_04_accountant(self):
        leases = self.env['re.lease'].with_user(self.accountant).search([])
        self.assertTrue({self.lease1, self.lease2} <= set(leases))
        with self.assertRaises(AccessError):
            self.lease1.with_user(self.accountant).write({'note': 'x'})
        self.assertTrue(self.env['re.tenant.ageing'].with_user(self.accountant).check_access('read') is None)

    def test_05_investor(self):
        props = self.env['re.property'].with_user(self.investor).search([])
        self.assertEqual(props, self.property2, 'investor sees only the properties they invest in')
        with self.assertRaises(AccessError):
            self.property2.with_user(self.investor).write({'name': 'x'})
        with self.assertRaises(AccessError):
            self.env['re.lease'].with_user(self.investor).search([])
        data = self.env['re.analytics'].with_user(self.investor).get_dashboard_data({})
        self.assertEqual(data['property_ids'], self.property2.ids)

    def test_06_tenant_portal(self):
        portal = new_test_user(self.env, login='re_tenant_portal', groups='base.group_portal',
                               partner_id=self.tenant.id)
        leases = self.env['re.lease'].with_user(portal).search([])
        self.assertEqual(leases, self.lease1)
        with self.assertRaises(AccessError):
            self.lease2.with_user(portal).read(['name'])
        with self.assertRaises(AccessError):
            self.env['re.property'].with_user(portal).search([])
        with self.assertRaises(AccessError):
            self.env['re.lease'].with_user(portal).create({'tenant_id': self.tenant.id})
        ticket = self.env['re.tenant.ticket'].create({'subject': 'Noise', 'partner_id': self.other_tenant.id,
                                                      'lease_id': self.lease2.id})
        self.assertNotIn(ticket, self.env['re.tenant.ticket'].with_user(portal).search([]))

    def test_07_contractor_portal(self):
        contractor = self.env['res.partner'].create({'name': 'FixIt Ltd', 're_is_contractor': True, 'is_company': True})
        portal = new_test_user(self.env, login='re_contractor_portal', groups='base.group_portal',
                               partner_id=contractor.id)
        job = self.env['re.work.order'].create({'title': 'Job', 'property_id': self.property.id,
                                                'contractor_id': contractor.id})
        other = self.env['re.work.order'].create({'title': 'Other job', 'property_id': self.property.id})
        visible = self.env['re.work.order'].with_user(portal).search([])
        self.assertEqual(visible, job)
        with self.assertRaises(AccessError):
            other.with_user(portal).read(['title'])
        with self.assertRaises(AccessError):
            job.with_user(portal).write({'title': 'x'})

    def test_08_audit_log_immutable(self):
        log = self.env['re.approval.log'].search([], limit=1)
        self.assertTrue(log)
        with self.assertRaises(Exception):
            log.with_user(self.approver).write({'note': 'tamper'})
        with self.assertRaises(Exception):
            log.with_user(self.approver).unlink()
