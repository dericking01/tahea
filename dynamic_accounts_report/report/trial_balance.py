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
                # Ensure all numeric values are properly formatted as floats
                report_data = data.get('report_data')
                
                # Process account data to ensure proper number formatting
                account_data = []
                for account in report_data.get('report_lines', []):
                    processed_account = {}
                    for key, value in account.items():
                        if isinstance(value, dict):
                            # Process debit/credit dictionaries
                            processed_dict = {}
                            for k, v in value.items():
                                try:
                                    processed_dict[k] = float(v or 0)
                                except (TypeError, ValueError):
                                    processed_dict[k] = 0.0
                            processed_account[key] = processed_dict
                        elif key in ['debit', 'credit', 'balance']:
                            try:
                                processed_account[key] = float(value or 0)
                            except (TypeError, ValueError):
                                processed_account[key] = 0.0
                        else:
                            processed_account[key] = value
                    account_data.append(processed_account)
                
                # Ensure totals are floats
                debit_total = float(report_data.get('debit_total', 0) or 0)
                credit_total = float(report_data.get('credit_total', 0) or 0)

                data.update({
                    'account_data': account_data,
                    'Filters': report_data.get('filters', {}),
                    'debit_total': debit_total,
                    'credit_total': credit_total,
                    'company': self.env.company,
                    'res_company': self.env.company,
                    'current_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                
                # Ensure analytic_accounts exists in filters
                if 'analytic_accounts' not in data['Filters']:
                    data['Filters']['analytic_accounts'] = ['All']
                
                # Add Init_balance if date_from exists
                if data['Filters'].get('date_from'):
                    for account in data['account_data']:
                        if 'Init_balance' not in account:
                            account['Init_balance'] = {
                                'debit': 0.0,
                                'credit': 0.0
                            }
                            # Ensure Init_balance values are floats
                            account['Init_balance']['debit'] = float(account.get('Init_balance', {}).get('debit', 0) or 0)
                            account['Init_balance']['credit'] = float(account.get('Init_balance', {}).get('credit', 0) or 0)
        
        return data
