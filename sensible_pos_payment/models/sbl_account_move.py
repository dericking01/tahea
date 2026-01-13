# Powered by Sensible Consulting Services
# -*- coding: utf-8 -*-
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
from odoo import api, models


class SblAccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def action_open_pos_invoice_view(self):
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            "views": [(self.env.ref("account.view_out_invoice_tree").id, "list")],
            'target': 'current',
        }