# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    location_answer = fields.Char(
        string='Location',
        compute='_compute_location_answer',
        store=False,
    )

    @api.depends('user_input_line_ids.question_id', 'user_input_line_ids.skipped',
                 'user_input_line_ids.value_char_box', 'user_input_line_ids.value_text_box',
                 'user_input_line_ids.value_numerical_box', 'user_input_line_ids.value_date',
                 'user_input_line_ids.value_datetime', 'user_input_line_ids.suggested_answer_id',
                 'user_input_line_ids.matrix_row_id')
    def _compute_location_answer(self):
        for record in self:
            location_line = record.user_input_line_ids.filtered(
                lambda l: l.question_id.title
                and l.question_id.title.strip().lower() == 'location'
                and not l.skipped
            )
            if not location_line:
                record.location_answer = False
                continue

            line = location_line[0]
            if line.answer_type == 'char_box':
                record.location_answer = line.value_char_box
            elif line.answer_type == 'text_box':
                record.location_answer = line.value_text_box
            elif line.answer_type in ('numerical_box', 'scale'):
                record.location_answer = str(line.value_numerical_box or line.value_scale or '')
            elif line.answer_type == 'date':
                record.location_answer = str(line.value_date) if line.value_date else False
            elif line.answer_type == 'datetime':
                record.location_answer = str(line.value_datetime) if line.value_datetime else False
            elif line.answer_type == 'suggestion':
                if line.matrix_row_id:
                    record.location_answer = f'{line.suggested_answer_id.value}: {line.matrix_row_id.value}'
                else:
                    record.location_answer = line.suggested_answer_id.value
            else:
                record.location_answer = False
