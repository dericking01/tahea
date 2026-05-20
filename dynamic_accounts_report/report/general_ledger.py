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

    def _limit_pdf_move_lines(self, account_data, max_detail_lines=2000):
        """Limit detailed rows in PDF to avoid wkhtmltopdf memory crashes."""
        total_lines = sum(len(acc.get('move_lines', [])) for acc in account_data)
        if total_lines <= max_detail_lines:
            return account_data, False

        trimmed = []
        running = 0
        for account in account_data:
            lines = account.get('move_lines', [])
            if running >= max_detail_lines:
                allowed = []
            else:
                remaining = max_detail_lines - running
                allowed = lines[:remaining]
                running += len(allowed)

            account_copy = dict(account)
            account_copy['move_lines'] = allowed
            trimmed.append(account_copy)

        note = (
            "Detailed lines were truncated for PDF stability "
            f"({max_detail_lines}/{total_lines} shown). "
            "Use XLSX export for the complete ledger details."
        )
        return trimmed, note

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('trial_pdf_report'):
            if data and data.get('wizard_id'):
                wizard = self.env['account.general.ledger'].browse(
                    int(data.get('wizard_id')))
                title = data.get('title') or wizard.titles or 'General Ledger'
                report_data = wizard.view_report([wizard.id], title)
                account_data, pdf_note = self._limit_pdf_move_lines(
                    report_data.get('report_lines', []))
                data.update(
                    {'doc_ids': docids,
                     'account_data': account_data,
                     'Filters': report_data.get('filters', {}),
                     'debit_total': report_data.get('debit_total', 0.0),
                     'credit_total': report_data.get('credit_total', 0.0),
                     'title': report_data.get('name', title),
                     'company': self.env.company,
                     'pdf_note': pdf_note,
                     })
            elif data and data.get('report_data'):
                account_data, pdf_note = self._limit_pdf_move_lines(
                    data.get('report_data')['report_lines'])
                data.update(
                    {'doc_ids': docids,
                     'account_data': account_data,
                     'Filters': data.get('report_data')['filters'],
                     'debit_total': data.get('report_data')['debit_total'],
                     'credit_total': data.get('report_data')['credit_total'],
                     'title': data.get('report_data')['name'],
                     'company': self.env.company,
                     'pdf_note': pdf_note,
                     })
        return data
