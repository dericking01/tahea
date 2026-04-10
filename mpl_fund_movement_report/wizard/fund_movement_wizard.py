# -*- coding: utf-8 -*-
#
#    Meghsundar Private Limited(<https://www.meghsundar.com>).
#
#
from odoo import fields, models, api


class FundMovementWizard(models.TransientModel):
    _name = 'fund.movement.wizard'
    _description = 'Fund Movement Wizard'

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    investment_adm = fields.Selection([
        ('nicol', 'NICOL'),
        ('old', 'OLD MUTUAL'),
        ('cont', 'CONTINENTAL'),
        ('zamara', 'ZAMARA'),
    ], string='Investment Admin', default='zamara', required=True)

    def print_report(self):
        self.ensure_one()
        data = {'ids': self.env.context.get('active_ids', [])}
        res = self.read()
        res = res and res[0] or {}
        data.update({'form': res})
        return self.env.ref('mpl_fund_movement_report.action_fund_movement_report').report_action(self, data=data)
