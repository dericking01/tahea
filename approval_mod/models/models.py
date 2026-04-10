# -*- coding: utf-8 -*-

from odoo import models, fields, api


class approval_mod(models.Model):
    _inherit = 'approval.request'

    department = fields.Many2one("hr.department","Department")
    project = fields.Many2one("account.analytic.account","Project")
    budget = fields.Many2one("crossovered.budget", "Budget")
