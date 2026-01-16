# -*- coding: utf-8 -*-

from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        for picking in self:
            # Capture user or scheduled date BEFORE validation
            effective_date = picking.date_done or picking.scheduled_date

            res = super(StockPicking, picking).button_validate()

            # Restore effective date AFTER validation
            if effective_date:
                picking.write({
                    'date_done': effective_date
                })

        return res
