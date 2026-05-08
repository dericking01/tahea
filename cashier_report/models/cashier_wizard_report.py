from odoo import models, fields
from io import BytesIO
import base64
import xlsxwriter
from datetime import datetime


class CashierReportWizard(models.TransientModel):
    _name = "cashier.report.wizard"
    _description = "Periodic Cashier Report Wizard"

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    sale_type = fields.Selection([
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail')
    ], string="Sale Type", help="Select to filter; leave empty to include both")
    shop_ids = fields.Many2many('pos.config', string="Shops", help="Select shops; leave empty to include all")

    excel_file = fields.Binary("Download Excel")
    file_name = fields.Char("File Name")

    def action_export_excel(self):
        # Build domain
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date)
        ]
        if self.sale_type:
            domain.append(('sale_type', '=', self.sale_type))
        if self.shop_ids:
            domain.append(('shop_id', 'in', self.shop_ids.ids))

        reports = self.env['cashier.report'].search(domain)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Cashier Report")

        # Formats
        bold_center = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#D9E1F2', 'border': 1
        })
        money_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        text_format = workbook.add_format({'border': 1})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
        subtotal_format = workbook.add_format({'bold': True, 'bg_color': '#FCE4D6', 'border': 1})

        # Column widths
        sheet.set_column('A:A', 12)  # Date
        sheet.set_column('B:B', 20)  # Shop
        sheet.set_column('C:C', 12)  # Sale Type
        sheet.set_column('D:D', 20)  # Cashier
        sheet.set_column('E:E', 18)  # Payment Method
        sheet.set_column('F:F', 15)  # Total Sales
        sheet.set_column('G:G', 20)  # Payment Ref
        sheet.set_column('H:H', 18)  # Total Expenditure
        sheet.set_column('I:I', 15)  # Balance

        # Title
        sheet.merge_range(
            'A1:I1',
            f"Cashier Report from {self.start_date} to {self.end_date}",
            workbook.add_format({'bold': True, 'align': 'center', 'font_size': 14})
        )

        # Headers
        headers = [
            'Date', 'Shop', 'Sale Type', 'Cashier',
            'Payment Method', 'Total Sales',
            'Payment Ref', 'Total Expenditure', 'Balance'
        ]
        for col, header in enumerate(headers):
            sheet.write(2, col, header, bold_center)

        row = 3
        for report in reports:
            shop_name = report.shop_id.name if report.shop_id else 'Undefined Shop'
            sale_type_name = report.sale_type or 'Undefined Sale Type'
            cashier_name = report.employee_id.name if report.employee_id else 'Unknown'

            # Collect payment and expenditure lines
            lines = []
            for line in getattr(report, 'line_ids', []):
                lines.append({
                    'payment_method': getattr(line.payment_method_id, 'name', 'Unknown'),
                    'total_sales': line.amount or 0.0,
                    'payment_ref': getattr(line, 'transaction_ref', '') or '',
                    'total_expenditure': 0.0
                })
            for exp in getattr(report, 'expenditure_ids', []):
                lines.append({
                    'payment_method': 'Expenditure',
                    'total_sales': 0.0,
                    'payment_ref': '',
                    'total_expenditure': exp.amount or 0.0
                })

            if not lines:
                lines.append({
                    'payment_method': '',
                    'total_sales': 0.0,
                    'payment_ref': '',
                    'total_expenditure': 0.0
                })

            num_lines = len(lines)
            total_sales_sum = sum(l['total_sales'] for l in lines)
            total_expenditure_sum = sum(l['total_expenditure'] for l in lines)

            # Merge main columns (Date, Shop, Sale Type, Cashier)
            sheet.merge_range(row, 0, row + num_lines - 1, 0, report.date, date_format)
            sheet.merge_range(row, 1, row + num_lines - 1, 1, shop_name, text_format)
            sheet.merge_range(row, 2, row + num_lines - 1, 2, sale_type_name, text_format)
            sheet.merge_range(row, 3, row + num_lines - 1, 3, cashier_name, text_format)

            # Write each line
            for i, line_data in enumerate(lines):
                sheet.write(row + i, 4, line_data['payment_method'], text_format)
                sheet.write_number(row + i, 5, line_data['total_sales'], money_format)
                sheet.write(row + i, 6, line_data['payment_ref'], text_format)
                sheet.write_number(row + i, 7, line_data['total_expenditure'], money_format)
                sheet.write_number(row + i, 8, line_data['total_sales'] - line_data['total_expenditure'], money_format)

            # Subtotal per shop
            row += num_lines
            sheet.merge_range(row, 0, row, 5, f"Subtotal for {shop_name}", subtotal_format)
            sheet.write_blank(row, 6, None, subtotal_format)
            sheet.write_number(row, 7, total_expenditure_sum, subtotal_format)
            sheet.write_number(row, 8, total_sales_sum - total_expenditure_sum, subtotal_format)
            sheet.write_number(row, 5, total_sales_sum, subtotal_format)
            row += 2  # Blank row

        workbook.close()
        output.seek(0)

        self.excel_file = base64.b64encode(output.read())
        self.file_name = f"Cashier_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cashier.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
