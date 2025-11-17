# -*- coding: utf-8 -*-
# from odoo import http


# class HrEmployeeExtended(http.Controller):
#     @http.route('/hr_employee_extended/hr_employee_extended', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hr_employee_extended/hr_employee_extended/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hr_employee_extended.listing', {
#             'root': '/hr_employee_extended/hr_employee_extended',
#             'objects': http.request.env['hr_employee_extended.hr_employee_extended'].search([]),
#         })

#     @http.route('/hr_employee_extended/hr_employee_extended/objects/<model("hr_employee_extended.hr_employee_extended"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hr_employee_extended.object', {
#             'object': obj
#         })
