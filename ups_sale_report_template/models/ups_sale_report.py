# -*- coding: utf-8 -*-
from odoo import api, fields, models

class UpsSalesReport(models.Model):
    _name = "ups.sale.report"
    _description = "ups Sale Report"

    name = fields.Char(string="Template Name", required=True)
    primary_color = fields.Char(string="Primary Color")
    secondary_color = fields.Char(string="Secondary Color")
    watermark = fields.Binary(string="Watermark")