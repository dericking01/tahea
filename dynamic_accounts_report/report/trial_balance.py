# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, models
from odoo.tools import date_utils
import json
import datetime

class TrialBalance(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.trial_balance'

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('trial_pdf_report'):
            if data.get('report_data'):
                data.update({
                    'account_data': data.get('report_data')['report_lines'],
                    'Filters': data.get('report_data')['filters'],
                    'debit_total': data.get('report_data')['debit_total'],
                    'credit_total': data.get('report_data')['credit_total'],
                    'company': self.env.company,
                    'res_company': self.env.company,  # Added for currency formatting
                    'current_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                
                # Ensure analytic_accounts exists in filters
                if 'analytic_accounts' not in data.get('report_data')['filters']:
                    data['Filters']['analytic_accounts'] = ['All']
                
                # Add Init_balance to account_data if date_from exists
                if data.get('report_data')['filters'].get('date_from'):
                    for account in data['account_data']:
                        if 'Init_balance' not in account:
                            account['Init_balance'] = {
                                'debit': 0.0,
                                'credit': 0.0
                            }
        
        return data
