# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

import werkzeug
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EmployeeSurvey(models.Model):
    _name = 'hr.employee.survey'
    _description = 'Employee Survey'

    def send_survey_to_employee(self):
        template_id = self.env.ref('dev_employee_multi_survey.template_dev_employee_multi_survey_send_survey')
        if template_id and self.employee_id and self.employee_id.work_email:
            template_id.email_from = self.env.user and self.env.user.company_id and self.env.user.company_id.email or ''
            template_id.email_to = self.employee_id.work_email
            template_id.send_mail(self.id, force_send=True)

    def start_survey_for_employee(self):
        survey_url = werkzeug.urls.url_join(self.survey_id.get_base_url(), self.survey_id.get_start_url()) if self.survey_id else False
        return {
            'type': 'ir.actions.act_url',
            'name': "Start Survey",
            'target': 'new',
            'url': survey_url,
        }

    def print_survey(self):
        if self.survey_answer_id:
            res = self.survey_answer_id.sudo().action_print_answers()
            res.update({'target': 'new'})
            return res
        else:
            raise ValidationError(_('''No Answer found for '%s' Survey''') % (self.survey_id.title))

    def _compute_survey_answer_id(self):
        for rec in self:
            answer_id = False
            partner_id = rec.employee_id and rec.employee_id.user_id and rec.employee_id.user_id.partner_id or False
            if partner_id:
                last_answer_id  = self.env['survey.user_input'].search([('survey_id', '=', rec.survey_id.id),
                                                                        ('partner_id', '=', partner_id.id)], order='id desc', limit=1)
                if last_answer_id:
                    answer_id = last_answer_id.id
            rec.survey_answer_id = answer_id

    def get_survey_url(self):
        survey_url = werkzeug.urls.url_join(self.survey_id.get_base_url(),
                                            self.survey_id.get_start_url()) if self.survey_id else False
        return survey_url

    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='cascade') # link
    survey_id = fields.Many2one('survey.survey', string='Survey', required=True)
    survey_answer_id = fields.Many2one('survey.user_input', string='Answer', compute='_compute_survey_answer_id')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: