from odoo import models
import datetime

class CashierReportPrint(models.AbstractModel):
    _name = 'report.cashier_report.report_cashier_pdf'
    _description = 'Cashier Report PDF'

    def _get_report_values(self, docids, data=None):
        docs = self.env['cashier.report'].browse(docids)
        company = self.env.company
        return {
            'doc_ids': docids,
            'doc_model': 'cashier.report',
            'docs': docs,
            'today': datetime.date.today(),
            'user': self.env.user,
            'company': company,
        }
