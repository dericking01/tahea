# -*- coding: utf-8 -*-
# from odoo import http


# class EmployeeCustom(http.Controller):
#     @http.route('/employee_custom/employee_custom', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/employee_custom/employee_custom/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('employee_custom.listing', {
#             'root': '/employee_custom/employee_custom',
#             'objects': http.request.env['employee_custom.employee_custom'].search([]),
#         })

#     @http.route('/employee_custom/employee_custom/objects/<model("employee_custom.employee_custom"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('employee_custom.object', {
#             'object': obj
#         })
