# -*- coding: utf-8 -*-

from odoo import models, fields, api


class appraisal_cust(models.Model):
    _inherit = 'survey.user_input'
    # suvery_id = fields.Many2one('survey.survey')
    department = fields.Many2one('hr.department', related='survey_id.department_id', string='Department', store = True)
    appraisal_period = fields.Char(compute='_compute_appraisal_period', store = True)
    appraiser_user = fields.Char(compute='_compute_appraiser_user', store = True)

    def _compute_appraiser_user(self):
        self.appraiser_user = "Skipped"
        for user_input in self:
            for line in user_input.user_input_line_ids:
                if line.question_id.display_name == 'Appraiser' and not line.skipped:
                    user_input.appraiser_user = line.display_name
                    break

    def _compute_appraisal_period(self):
        self.appraisal_period = "Skipped"
        for user_input in self:
            for line in user_input.user_input_line_ids:
                if line.question_id.display_name == 'Appraisal for Period' and not line.skipped:
                    user_input.appraisal_period = line.display_name
                    break

class HrDep(models.Model):
    _inherit = 'survey.survey'

    department_id = fields.Many2one('hr.department', string='Department')
