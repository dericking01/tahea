# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestPropertyLeasing(ReCommon):

    def test_01_property_hierarchy(self):
        """Test 1: property -> building -> floor -> 5 units, with navigation."""
        self.assertEqual(len(self.units), 5)
        self.assertEqual(self.property.building_count, 1)
        self.assertEqual(self.property.unit_count, 5)
        self.assertEqual(self.building.floor_count, 1)
        self.assertEqual(self.floor.unit_count, 5)
        self.assertTrue(self.property.analytic_account_id, 'property gets an analytic account')
        self.assertTrue(self.building.analytic_account_id, 'building gets an analytic account')
        self.assertAlmostEqual(self.property.lettable_area_sqm, sum([60, 70, 80, 90, 100]))
        action = self.property.action_view_units()
        self.assertEqual(self.env['re.unit'].search(action['domain']), self.units)
        action = self.building.action_view_units()
        self.assertEqual(self.env['re.unit'].search(action['domain']), self.units)
        self.assertEqual(self.units[0].display_name, 'MSH / A / A-1')
        # a unit cannot point to a floor of another building
        other = self.env['re.building'].create({'name': 'Block B', 'property_id': self.property.id})
        floor_b = self.env['re.floor'].create({'name': 'B0', 'building_id': other.id})
        with self.assertRaises(ValidationError):
            self.units[0].floor_id = floor_b
        # land properties cannot contain buildings
        land = self.env['re.property'].create({
            'name': 'Kigamboni Land', 'code': 'KGL', 'property_type_id': self.env.ref(
                'real_estate_lifecycle.property_type_land').id, 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self.env['re.building'].create({'name': 'X', 'property_id': land.id})
        wiz = self.env['re.land.subdivide.wizard'].create({'property_id': land.id, 'count': 4, 'area': 600})
        wiz.action_subdivide()
        self.assertEqual(len(land.unit_ids), 4)
        self.assertTrue(all(land.unit_ids.mapped('is_plot')))

    def test_02_lease_lifecycle_and_occupancy(self):
        """Test 2: register tenant, create lease, approve and activate; occupancy follows."""
        unit = self.units[0]
        self.assertEqual(unit.occupancy_status, 'vacant')
        self.assertEqual(unit.rental_status, 'available')
        lease = self._make_lease(deposit_amount=4_000_000)
        self.assertTrue(self.tenant.re_is_tenant)
        lease.with_user(self.pm).action_submit()
        self.assertEqual(lease.state, 'to_approve')
        self.assertEqual(unit.rental_status, 'reserved')
        # segregation of duties: the requester cannot approve, nor can a leasing-level user
        with self.assertRaises(AccessError):
            lease.with_user(self.pm).action_approve()
        lease.with_user(self.approver).action_approve()
        self.assertEqual(lease.state, 'approved')
        self.assertEqual(lease.re_approved_by_id, self.approver)
        lease.action_activate()
        self.assertEqual(lease.state, 'active')
        self.assertEqual(unit.occupancy_status, 'occupied')
        self.assertEqual(unit.rental_status, 'let')
        self.assertEqual(unit.tenant_id, self.tenant)
        self.assertEqual(len(lease.deposit_ids), 1, 'deposit record created on activation')
        self.assertTrue(lease.schedule_ids, 'billing schedule generated')
        logs = self.env['re.approval.log'].search([('res_model', '=', 're.lease'), ('res_id', '=', lease.id)])
        self.assertEqual(set(logs.mapped('action')), {'requested', 'approved'})
        # commercial terms are locked after submission
        with self.assertRaises(UserError):
            lease.rent_amount = 1
        # overlapping lease on the same unit is refused
        other = self._make_lease(tenant=self.env['res.partner'].create({'name': 'Other'}), start='2026-06-01')
        with self.assertRaises(ValidationError):
            other.with_user(self.pm).action_submit()
        # termination vacates the unit
        wiz = self.env['re.lease.terminate.wizard'].create({
            'lease_id': lease.id, 'termination_date': '2026-08-31', 'termination_type': 'mutual',
            'reason': 'Relocation'})
        wiz.action_terminate()
        self.assertEqual(lease.state, 'terminated')
        self.assertEqual(unit.occupancy_status, 'vacant')
        self.assertFalse(lease.schedule_ids.filtered(lambda s: s.period_start > lease.effective_end_date),
                         'no pending billing after termination')

    def test_03_renewal(self):
        lease = self._activate(self._make_lease(end='2026-12-31'))
        wiz = self.env['re.lease.renew.wizard'].create({'lease_id': lease.id})
        self.assertEqual(str(wiz.date_start), '2027-01-01')
        action = wiz.action_renew()
        renewal = self.env['re.lease'].browse(action['res_id'])
        self.assertEqual(renewal.parent_lease_id, lease)
        self._activate(renewal)
        self.assertEqual(lease.state, 'renewed')
        self.assertEqual(renewal.state, 'active')

    def test_04_crm_pipeline_to_lease(self):
        lead = self.env['crm.lead'].create({
            'name': 'Enquiry A-2', 're_is_rental': True, 'partner_id': self.tenant.id,
            're_property_id': self.property.id, 're_unit_ids': [(6, 0, self.units[1].ids)],
            're_lease_type_id': self.lease_type.id, 're_proposed_rent': 1_800_000, 'type': 'opportunity'})
        with self.assertRaises(UserError):
            lead.action_re_create_lease()
        lead.action_re_submit_application()
        lead.re_screening_state = 'passed'
        action = lead.action_re_create_lease()
        lease = self.env['re.lease'].browse(action['res_id'])
        self.assertEqual(lease.state, 'draft')
        self.assertEqual(lease.rent_amount, 1_800_000)
        self.assertEqual(lease.unit_ids, self.units[1])
        self.assertEqual(lease.crm_lead_id, lead)
