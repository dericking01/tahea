# -*- coding: utf-8 -*-

from odoo import api, fields, models


def _extract_line_value(line):
    if line.answer_type == 'char_box':
        return line.value_char_box or False
    if line.answer_type == 'text_box':
        return line.value_text_box or False
    if line.answer_type == 'numerical_box':
        return str(line.value_numerical_box) if line.value_numerical_box is not None else False
    if line.answer_type == 'scale':
        return str(line.value_scale) if line.value_scale is not None else False
    if line.answer_type == 'date':
        return str(line.value_date) if line.value_date else False
    if line.answer_type == 'datetime':
        return str(line.value_datetime) if line.value_datetime else False
    if line.answer_type == 'suggestion':
        if line.matrix_row_id:
            return f'{line.suggested_answer_id.value}: {line.matrix_row_id.value}'
        return line.suggested_answer_id.value or False
    return False


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    configured_answer_ids = fields.One2many(
        'survey.user_input.configured_answer',
        'user_input_id',
        string='Key Answers',
    )
    configured_answers_summary = fields.Char(
        string='Key Answers',
        compute='_compute_configured_answers_summary',
        store=True,
    )

    @api.depends('configured_answer_ids.value', 'configured_answer_ids.column_name',
                 'configured_answer_ids.column_id')
    def _compute_configured_answers_summary(self):
        for record in self:
            parts = [
                f"{a.column_name}: {a.value}"
                for a in record.configured_answer_ids.sorted('column_id')
                if a.value
            ]
            record.configured_answers_summary = ' | '.join(parts) if parts else False

    def _sync_configured_answers(self):
        columns = self.env['survey.participation.column'].sudo().search([])
        ConfiguredAnswer = self.env['survey.user_input.configured_answer'].sudo()

        for record in self:
            # Remove answers whose column is inactive or deleted
            stale = ConfiguredAnswer.search([
                ('user_input_id', '=', record.id),
                ('column_id', 'not in', columns.ids),
            ])
            if stale:
                stale.unlink()

            for column in columns:
                qt = column.question_title.strip().lower()
                matching_line = record.user_input_line_ids.filtered(
                    lambda l, _qt=qt: l.question_id.title
                    and l.question_id.title.strip().lower() == _qt
                    and not l.skipped
                )
                value = _extract_line_value(matching_line[0]) if matching_line else False

                existing = ConfiguredAnswer.search([
                    ('user_input_id', '=', record.id),
                    ('column_id', '=', column.id),
                ], limit=1)

                if existing:
                    if value:
                        existing.value = value
                    else:
                        existing.unlink()
                elif value:
                    ConfiguredAnswer.create({
                        'user_input_id': record.id,
                        'column_id': column.id,
                        'value': value,
                    })


class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    _ANSWER_FIELDS = frozenset({
        'value_char_box', 'value_text_box', 'value_numerical_box', 'value_scale',
        'value_date', 'value_datetime', 'suggested_answer_id', 'matrix_row_id',
        'skipped', 'question_id',
    })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('user_input_id')._sync_configured_answers()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self._ANSWER_FIELDS & set(vals):
            self.mapped('user_input_id')._sync_configured_answers()
        return res


class SurveyUserInputConfiguredAnswer(models.Model):
    _name = 'survey.user_input.configured_answer'
    _description = 'Survey User Input Configured Answer'
    _order = 'column_id'

    user_input_id = fields.Many2one(
        'survey.user_input', required=True, ondelete='cascade', index=True,
    )
    column_id = fields.Many2one(
        'survey.participation.column', required=True, ondelete='cascade',
    )
    column_name = fields.Char(related='column_id.name', store=True, string='Field')
    value = fields.Char('Answer')
