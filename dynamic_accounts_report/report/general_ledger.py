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


class GeneralLedger(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.general_ledger'

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('trial_pdf_report'):
            if data and data.get('wizard_id'):
                wizard = self.env['account.general.ledger'].browse(
                    int(data.get('wizard_id')))
                title = data.get('title') or wizard.titles or 'General Ledger'
                report_data = wizard.view_report([wizard.id], title)
                data.update(
                    {'doc_ids': docids,
                     'account_data': report_data.get('report_lines', []),
                     'Filters': report_data.get('filters', {}),
                     'debit_total': report_data.get('debit_total', 0.0),
                     'credit_total': report_data.get('credit_total', 0.0),
                     'title': report_data.get('name', title),
                     'company': self.env.company,
                     })
            elif data and data.get('report_data'):
                data.update(
                    {'doc_ids': docids,
                     'account_data': data.get('report_data')['report_lines'],
                     'Filters': data.get('report_data')['filters'],
                     'debit_total': data.get('report_data')['debit_total'],
                     'credit_total': data.get('report_data')['credit_total'],
                     'title': data.get('report_data')['name'],
                     'company': self.env.company,
                     })
        return data
