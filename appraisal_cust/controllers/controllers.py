# -*- coding: utf-8 -*-
# from odoo import http


# class AppraisalCust(http.Controller):
#     @http.route('/appraisal_cust/appraisal_cust', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/appraisal_cust/appraisal_cust/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('appraisal_cust.listing', {
#             'root': '/appraisal_cust/appraisal_cust',
#             'objects': http.request.env['appraisal_cust.appraisal_cust'].search([]),
#         })

#     @http.route('/appraisal_cust/appraisal_cust/objects/<model("appraisal_cust.appraisal_cust"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('appraisal_cust.object', {
#             'object': obj
#         })
