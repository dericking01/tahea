# -*- coding: utf-8 -*-
# from odoo import http


# class CustomPayrollReport(http.Controller):
#     @http.route('/custom_payroll_report/custom_payroll_report', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_payroll_report/custom_payroll_report/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_payroll_report.listing', {
#             'root': '/custom_payroll_report/custom_payroll_report',
#             'objects': http.request.env['custom_payroll_report.custom_payroll_report'].search([]),
#         })

#     @http.route('/custom_payroll_report/custom_payroll_report/objects/<model("custom_payroll_report.custom_payroll_report"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_payroll_report.object', {
#             'object': obj
#         })

