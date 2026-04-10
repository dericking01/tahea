# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResPartnerMember(models.Model):
    _inherit = "res.partner"

    empl_no =fields.Char(string="EMPL NO")
    ni_number = fields.Char(string="NI NUMBER")
    dofa = fields.Date(string="DoFA")
    # village =fields.Char(string="Village")
    # district = fields.Char(string="District")
    # t/i = fields.Char(string="T/I")
