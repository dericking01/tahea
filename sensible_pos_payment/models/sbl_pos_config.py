# Powered by Sensible Consulting Services
# -*- coding: utf-8 -*-
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    sbl_enable_pos_payment = fields.Boolean('Enable POS Payment')