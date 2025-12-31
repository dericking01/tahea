# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _

class pos_config(models.Model):
    _inherit = 'pos.config' 

    allow_kitchens_receipt = fields.Boolean('Allow Kitchen Receipt', default=True)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_kitchens_receipt = fields.Boolean(related='pos_config_id.allow_kitchens_receipt', readonly=False)