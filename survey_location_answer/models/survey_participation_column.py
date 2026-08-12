# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SurveyParticipationColumn(models.Model):
    _name = 'survey.participation.column'
    _description = 'Survey Participation Column'
    _order = 'sequence, id'

    name = fields.Char('Column Label', required=True)
    question_id = fields.Many2one(
        'survey.question',
        string='Question',
        domain=[('is_page', '=', False)],
        help="Pick from any existing question. The title auto-fills below and is used "
             "to match answers across all surveys.",
    )
    question_title = fields.Char(
        'Question Title',
        required=True,
        compute='_compute_question_title',
        store=True,
        readonly=False,
        help="Case-insensitive match on the question title. "
             "Auto-filled when you select a question above, but can be typed manually.",
    )
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    @api.depends('question_id')
    def _compute_question_title(self):
        for rec in self:
            if rec.question_id:
                rec.question_title = rec.question_id.title
            elif not rec.question_title:
                rec.question_title = False

    @api.onchange('question_id')
    def _onchange_question_id(self):
        if self.question_id and not self.name:
            self.name = self.question_id.title

    def _trigger_answer_sync(self):
        self.env['survey.user_input'].sudo().search([])._sync_configured_answers()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._trigger_answer_sync()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._trigger_answer_sync()
        return res
