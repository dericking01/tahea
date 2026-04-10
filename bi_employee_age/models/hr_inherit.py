# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import datetime

class HrInherit(models.Model):
	_inherit = 'hr.employee'

	employee_age = fields.Integer(string="Age",compute='_compute_age');
	

	@api.depends("birthday")
	def _compute_age(self):
		for rec in self:
			rec.employee_age = relativedelta(datetime.date.today(),rec.birthday).years;
