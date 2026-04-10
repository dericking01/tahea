# -*- coding: utf-8 -*-
#
#    Meghsundar Private Limited(<https://www.meghsundar.com>).
#
import datetime

from odoo import fields, models, api


class FundMovementReport(models.TransientModel):
    _name = "report.mpl_fund_movement_report.fund_movement_report"

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def _get_report_values(self, docids, data=None):
        investment_ids = self.env['bt.asset.investment'].sudo().search(
            [('investment_adm', '=', data['form']['investment_adm'])])
        line_ids = self.env['bt.asset.code.line'].sudo().search(['&', '&',
                                                                 ('investment_id', 'in', investment_ids.ids),
                                                                 ('date', '>=', data['form']['start_date']),
                                                                 ('date', '<=', data['form']['end_date'])
                                                                 ])
        debit = round(sum(line_ids.mapped('debit')), 2)
        credit = round(sum(line_ids.mapped('price_cost')), 2)
        balance = round((debit - credit), 2)
        docs = self.env['res.company'].browse(self.env.company.id)
        return {
            'reporting_date': datetime.date.today().strftime('%d-%B-%Y'),
            'data': data,
            'lines': line_ids,
            'debit': debit,
            'credit': credit,
            'balance': balance,
            'docs': docs,
        }
