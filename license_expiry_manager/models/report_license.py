from odoo import models, fields
import io
import base64
import xlsxwriter
from datetime import datetime

class LicenseReportWizard(models.TransientModel):
    _name = "license.report.wizard"
    _description = "Wizard to generate License Report Excel"

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    state = fields.Selection([
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], string="State")

    file_name = fields.Char(string="File Name")
    file_data = fields.Binary(string="Excel File", readonly=True)

    def action_generate_excel(self):
        # Force recompute of state to ensure computed field has value
        self.env['license.subscription'].search([])._compute_state()

        # Build domain based on wizard filters
        domain = []

        # Active during the period: overlap logic
        if self.start_date:
            domain.append(('expiry_date', '>=', self.start_date))  # Not expired before period starts
        if self.end_date:
            domain.append(('start_date', '<=', self.end_date))      # Started before period ends
        if self.state:
            domain.append(('state', '=', self.state))              # Filter by selected state

        records = self.env['license.subscription'].search(domain)

        # Safety check
        if not records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Data',
                    'message': 'No records found for selected filters.',
                    'type': 'warning',
                }
            }

        # Create in-memory Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("License Report")

        # FORMATS
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter'
        })
        header_format = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#D9D9D9'
        })
        text_format = workbook.add_format({'border': 1})
        date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})
        money_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})

        # TITLE
        worksheet.merge_range('A1:H1', 'LICENSE & SUBSCRIPTION REPORT', title_format)

        # FILTER INFO
        worksheet.write('A3', 'From:')
        worksheet.write('B3', str(self.start_date or 'All'))
        worksheet.write('D3', 'To:')
        worksheet.write('E3', str(self.end_date or 'All'))
        worksheet.write('G3', 'State:')
        worksheet.write('H3', self.state or 'All')

        # HEADERS
        headers = ['Name', 'Type', 'Vendor', 'Start Date', 'Expiry Date', 'State', 'Cost', 'Responsible']
        row = 4
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)

        # DATA
        row += 1
        for rec in records:
            worksheet.write(row, 0, rec.name or '', text_format)
            worksheet.write(row, 1, dict(rec._fields['type'].selection).get(rec.type), text_format)
            worksheet.write(row, 2, rec.vendor_id.name or '', text_format)
            worksheet.write(row, 3, rec.start_date or '', date_format)
            worksheet.write(row, 4, rec.expiry_date or '', date_format)
            worksheet.write(row, 5, dict(rec._fields['state'].selection).get(rec.state), text_format)
            worksheet.write(row, 6, rec.cost or 0.0, money_format)
            worksheet.write(row, 7, rec.responsible_id.name or '', text_format)
            row += 1

        # COLUMN WIDTHS
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 25)
        worksheet.set_column('D:E', 12)
        worksheet.set_column('F:F', 15)
        worksheet.set_column('G:G', 12)
        worksheet.set_column('H:H', 20)

        workbook.close()
        output.seek(0)

        # Encode to Binary for Odoo download
        self.file_data = base64.b64encode(output.read())
        self.file_name = f"License_Report_{datetime.today().strftime('%Y%m%d_%H%M')}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'license.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
