# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ReCommon


@tagged('post_install', '-at_install', 're_lpm')
class TestMaintenanceProcurement(ReCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.elevator = cls.env['maintenance.equipment'].create({
            'name': 'Passenger Lift 1', 're_property_id': cls.property.id, 're_building_id': cls.building.id,
            're_asset_category_id': cls.env.ref('real_estate_lifecycle.asset_category_elevator').id,
            're_replacement_cost': 120_000_000, 're_criticality': 'critical', 'serial_no': 'LIFT-0001',
            're_installation_date': '2005-01-01', 're_expected_life_years': 20})
        cls.contractor = cls.env['res.partner'].create({'name': 'LiftCare Ltd', 're_is_contractor': True,
                                                        'is_company': True})
        cls.contractor_b = cls.env['res.partner'].create({'name': 'Elevate TZ', 're_is_contractor': True,
                                                          'is_company': True})
        # tiered maintenance approval: >= 2M needs a maintenance manager (segregated)
        cls.env['re.approval.rule'].create({
            'name': 'WO >= 2M', 'document_type': 'work_order', 'min_amount': 2_000_000,
            'group_id': cls.env.ref('real_estate_lifecycle.group_re_maintenance_manager').id, 'segregation': True})
        cls.property.user_ids = [(4, cls.pm.id)]

    def test_01_maintenance_work_order(self):
        """Test 8: elevator, request, technician, approval, completion, expenditure,
        asset history and property expenditure."""
        self.assertTrue(self.elevator.re_asset_code.startswith('AST-'))
        wo = self.env['re.work.order'].with_user(self.pm).create({
            'title': 'Lift stuck on 3rd floor', 'property_id': self.property.id, 'building_id': self.building.id,
            'equipment_id': self.elevator.id, 'maintenance_type': 'corrective', 'estimated_cost': 3_000_000,
            'technician_id': self.technician.id, 'contractor_id': self.contractor.id, 'execution': 'contractor',
            'date_target': '2026-12-31'})
        self.assertEqual(wo.state, 'new')
        wo.with_user(self.pm).action_triage()
        wo.with_user(self.pm).action_submit_approval()
        self.assertEqual(wo.state, 'approval')
        self.assertEqual(wo.re_approval_rule_id.min_amount, 2_000_000)
        with self.assertRaises(AccessError):
            wo.with_user(self.pm).action_approve()
        wo.with_user(self.mm).action_approve()
        self.assertEqual(wo.state, 'assigned')
        self.assertEqual(wo.approved_budget, 3_000_000)
        # the technician sees and progresses only their own work order
        self.assertIn(wo, self.env['re.work.order'].with_user(self.technician).search([]))
        wo.with_user(self.technician).action_start()
        # expenditure: direct contractor bill within the approved budget
        action = wo.action_create_vendor_bill()
        bill = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(bill.re_work_order_id, wo)
        bill.invoice_line_ids.price_unit = 3_000_000
        bill.action_post()
        self.assertEqual(wo.actual_cost, 3_000_000)
        self.assertEqual(bill.invoice_line_ids.re_property_id, self.property)
        with self.assertRaises(UserError):
            wo.with_user(self.technician).action_complete()  # completion report missing
        wo.completion_report = '<p>Replaced door operator board.</p>'
        wo.with_user(self.technician).action_complete()
        self.assertEqual(wo.state, 'completed')
        wo.action_request_confirmation()
        self.assertEqual(wo.state, 'closed', 'no tenant requester: closed directly')
        # asset history & replacement analysis
        self.assertEqual(self.elevator.re_work_order_count, 1)
        self.assertEqual(self.elevator.re_maintenance_cost_total, 3_000_000)
        self.assertEqual(self.elevator.re_recommendation, 'replace',
                         'critical asset past its useful life is flagged for review (not replaced automatically)')
        # property expenditure report
        fin = self.env['re.analytics']._financials(self.property.ids, None, None)
        self.assertEqual(fin['maintenance'], 3_000_000)
        self.assertEqual(fin['opex'], 3_000_000)
        self.assertEqual(fin['noi'], -3_000_000)

    def test_02_emergency_and_overrun_controls(self):
        wo = self.env['re.work.order'].create({
            'title': 'Burst pipe', 'property_id': self.property.id, 'maintenance_type': 'corrective',
            'estimated_cost': 1_000_000, 'technician_id': self.technician.id, 'contractor_id': self.contractor.id,
            'execution': 'contractor'})
        wo.with_user(self.pm).action_emergency_start()
        self.assertEqual(wo.state, 'in_progress')
        self.assertEqual(wo.emergency_review_state, 'pending')
        with self.assertRaises(UserError):
            wo.with_user(self.pm).action_emergency_review()
        wo.with_user(self.mm).with_context(review_decision='accepted').action_emergency_review()
        self.assertEqual(wo.re_approval_state, 'approved')
        # a bill above the approved budget is blocked for non finance managers
        bill = self.env['account.move'].browse(wo.action_create_vendor_bill()['res_id'])
        bill.invoice_line_ids.price_unit = 1_500_000
        with self.assertRaises(UserError):
            bill.with_user(self.accountant).action_post()
        bill.with_user(self.fin_manager).action_post()
        self.assertTrue(self.env['re.exception'].search([('check_code', '=', 'control_override'),
                                                         ('res_id', '=', bill.id)]))
        wo.completion_report = '<p>done</p>'
        with self.assertRaises(UserError):
            wo.action_complete()  # actual exceeds approved budget
        wo.with_user(self.pm).action_request_supplementary()
        wo.with_user(self.pm).action_approve()  # under 2M: property-manager authority
        self.assertEqual(wo.approved_budget, 1_500_000)
        wo.action_complete()
        self.assertEqual(wo.state, 'completed')

    def test_03_vendor_procurement(self):
        """Test 11: quotation request, comparison, approval, PO, completion, vendor
        bill, expenditure recorded against the property."""
        wo = self.env['re.work.order'].create({
            'title': 'Repaint stairwell', 'property_id': self.property.id, 'building_id': self.building.id,
            'maintenance_type': 'corrective', 'technician_id': self.technician.id})
        wizard = self.env['re.rfq.wizard'].create({'work_order_id': wo.id,
                                                   'vendor_ids': [(6, 0, (self.contractor | self.contractor_b).ids)]})
        wizard.action_create_rfqs()
        self.assertEqual(len(wo.purchase_order_ids), 2)
        po_a = wo.purchase_order_ids.filtered(lambda p: p.partner_id == self.contractor)
        po_b = wo.purchase_order_ids - po_a
        po_a.order_line.price_unit = 4_500_000
        po_b.order_line.price_unit = 3_800_000
        self.assertEqual(po_b.order_line.analytic_distribution,
                         self.property._re_analytic_distribution(self.building))
        # PO cannot be confirmed before the budget is approved
        with self.assertRaises(UserError):
            po_b.with_user(self.accountant).button_confirm()
        po_b.action_re_select_for_work_order()
        self.assertEqual(wo.contractor_id, self.contractor_b)
        self.assertEqual(wo.estimated_cost, 3_800_000)
        wo.with_user(self.pm).action_submit_approval()
        wo.with_user(self.mm).action_approve()
        wo.action_confirm_selected_po()
        self.assertEqual(po_b.state, 'purchase')
        self.assertEqual(po_a.state, 'cancel')
        self.assertEqual(wo.committed_cost, 3_800_000)
        wo.action_start()
        wo.completion_report = '<p>Painted</p>'
        po_b.action_create_invoice()
        bill = po_b.invoice_ids
        self.assertEqual(bill.re_work_order_id, wo, 'bill linked to work order through the PO')
        bill.invoice_date = '2026-06-30'
        bill.action_post()
        self.assertEqual(wo.actual_cost, 3_800_000)
        self.assertEqual(bill.invoice_line_ids.re_property_id, self.property)
        self.assertEqual(bill.invoice_line_ids.re_building_id, self.building)
        wo.action_complete()
        self.assertEqual(wo.state, 'completed')
        self.assertEqual(self.contractor_b.re_jobs_assigned, 1)
        self.assertEqual(self.contractor_b.re_actual_spend, 3_800_000)
        fin = self.env['re.analytics']._financials(self.property.ids, None, None)
        self.assertEqual(fin['maintenance'], 3_800_000)
        # duplicate vendor bill detection
        dup = bill.copy({'invoice_date': bill.invoice_date, 'ref': 'INV-77'})
        bill2 = dup.copy({'ref': 'INV-77'})
        self.env['re.exception'].run_checks(['duplicate_vendor_bill'])
        self.assertTrue(self.env['re.exception'].search([('check_code', '=', 'duplicate_vendor_bill'),
                                                         ('res_id', 'in', (dup | bill2).ids)]))

    def test_04_preventive_plan_idempotent(self):
        plan = self.env['re.maintenance.plan'].create({
            'name': 'Quarterly lift service', 'property_id': self.property.id, 'equipment_id': self.elevator.id,
            'interval_number': 3, 'interval_type': 'months', 'next_date': '2026-11-25', 'lead_days': 7,
            'technician_id': self.technician.id, 'estimated_cost': 500_000})
        wos = plan._generate(today=date(2026, 11, 20))
        self.assertEqual(len(wos), 1)
        self.assertEqual(str(wos.scheduled_date), '2026-11-25')
        self.assertEqual(str(plan.next_date), '2027-02-25')
        again = plan._generate(today=date(2026, 11, 20))
        self.assertFalse(again)
