# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields


class Employee(models.Model):
    _inherit = 'hr.employee'

    employee_survey_ids = fields.One2many('hr.employee.survey', 'employee_id', string='Survey')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: