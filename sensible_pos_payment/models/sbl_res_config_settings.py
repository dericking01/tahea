# Powered by Sensible Consulting Services
# -*- coding: utf-8 -*-
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbl_enable_pos_payment = fields.Boolean(related='pos_config_id.sbl_enable_pos_payment', readonly=False)
