import base64

from odoo.tests import tagged

from odoo.addons.hr_holidays.tests.common import TestHrHolidaysCommon

# 1x1 black PNG
SIGNATURE = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c6360606060000000050001a5f645400000000049454e44ae426082'
))


@tagged('post_install', '-at_install')
class TestTimeOffSignature(TestHrHolidaysCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leave_type = cls.env['hr.leave.type'].create({
            'name': 'GW Unpaid',
            'requires_allocation': 'no',
            'leave_validation_type': 'manager',
        })

    def _leave(self, **vals):
        return self.env['hr.leave'].with_user(self.user_employee_id).create(dict({
            'name': 'Family event',
            'employee_id': self.employee_emp_id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': '2026-11-16',
            'request_date_to': '2026-11-17',
        }, **vals))

    def test_employee_signs_and_date_is_recorded(self):
        leave = self._leave()
        self.assertEqual(leave.state, 'confirm')
        self.assertFalse(leave.employee_signed_on)
        leave.with_user(self.user_employee_id).employee_signature = SIGNATURE
        self.assertTrue(leave.employee_signature)
        self.assertTrue(leave.employee_signed_on)
        leave.employee_signature = False
        self.assertFalse(leave.employee_signed_on)

        signed = self._leave(request_date_from='2026-11-23', request_date_to='2026-11-23',
                             employee_signature=SIGNATURE)
        self.assertTrue(signed.employee_signed_on)

    def test_signature_on_all_time_off_forms(self):
        for xmlid in ('hr_holidays.hr_leave_view_form',
                      'hr_holidays.hr_leave_view_form_manager',
                      'hr_holidays.hr_leave_view_form_dashboard_new_time_off'):
            view = self.env.ref(xmlid)
            arch = self.env['hr.leave'].get_views([(view.id, 'form')])['views']['form']['arch']
            self.assertIn('name="employee_signature"', arch, xmlid)
            self.assertIn('widget="signature"', arch, xmlid)

    def test_signature_printed_on_report(self):
        leave = self._leave(employee_signature=SIGNATURE)
        report = self.env.ref('gwambina_extended.action_report_time_off_request')
        self.assertEqual(report.binding_model_id.model, 'hr.leave')
        html = self.env['ir.actions.report']._render_qweb_html(report, leave.ids)[0].decode()
        self.assertIn('Employee Signature', html)
        self.assertIn('alt="Signature"', html)
        self.assertIn('Family event', html)
        pdf, fmt = self.env['ir.actions.report'].with_context(force_report_rendering=True)._render_qweb_pdf(report, leave.ids)
        self.assertEqual(fmt, 'pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))

        unsigned = self._leave(request_date_from='2026-11-30', request_date_to='2026-11-30')
        html = self.env['ir.actions.report']._render_qweb_html(report, unsigned.ids)[0].decode()
        self.assertNotIn('alt="Signature"', html)
