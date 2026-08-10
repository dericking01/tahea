from odoo import api, models


class StatementInvoiceReport(models.AbstractModel):
    """QWeb report data provider for the Custom Invoice Report PDF.

    Registered under ``report.<report_name>`` so Odoo's report engine calls
    ``_get_report_values`` automatically when rendering the PDF associated
    with ``ir.actions.report`` record
    ``custom_invoice_statement_report.action_report_statement_invoice``.
    """
    _name = 'report.custom_invoice_statement_report.invoice_doc'
    _description = "Custom Invoice Report Document"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['statement.invoice.report.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'statement.invoice.report.wizard',
            'docs': wizards,
            'report_data': wizards._get_report_data() if wizards else {},
        }
