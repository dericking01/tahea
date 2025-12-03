import base64
from datetime import datetime
from io import BytesIO
import xlsxwriter

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from xlsxwriter.utility import xl_rowcol_to_cell


class PayrollReportExcelWiz(models.TransientModel):
    _name = 'payroll.report.wiz'
    _description = 'Payroll Report Wizard'

    from_date = fields.Date('From Date', required=True)
    date_end = fields.Date('To Date', required=True)
    company = fields.Many2one('res.company', default=lambda self: self.env.company, string="Company")

    def get_rules(self):
        vals = []
        heads = self.env['hr.salary.rule'].search([('active', '=', True)], order='sequence asc')
        for head in heads:
            vals.append([head.name, head.code])
        return vals

    def get_item_data(self):
        file_name = _('payroll report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        heading_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True, 'size': 14})
        cell_text_format_n = workbook.add_format({'align': 'center', 'bold': True, 'size': 9})
        cell_text_format = workbook.add_format({'align': 'left', 'bold': True, 'size': 9})
        cell_text_format.set_border()

        cell_text_format_new = workbook.add_format({'align': 'left', 'size': 9})
        cell_text_format_new.set_border()

        cell_number_format = workbook.add_format({'align': 'right', 'bold': False, 'size': 9, 'num_format': '#,###0.00'})
        cell_number_format.set_border()

        normal_num_bold = workbook.add_format({'bold': True, 'num_format': '#,###0.00', 'size': 9})
        normal_num_bold.set_border()

        worksheet = workbook.add_worksheet('payroll report')
        for col in range(15):
            worksheet.set_column(col, col, 20)

        if self.from_date and self.date_end:
            payroll_month = self.from_date.strftime("%B")
            worksheet.merge_range('A1:F2', f'Payroll For {payroll_month} {self.from_date.year}', heading_format)
            worksheet.merge_range('B4:D4', self.company.name or '', cell_text_format_n)

            row = 2
            worksheet.write(row + 1, 0, 'Company', cell_text_format_n)
            worksheet.write(row, 4, 'Date From', cell_text_format_n)
            worksheet.write(row, 5, self.from_date.strftime('%d-%m-%Y') or '')
            row += 1
            worksheet.write(row, 4, 'Date To', cell_text_format_n)
            worksheet.write(row, 5, self.date_end.strftime('%d-%m-%Y') or '')
            row += 2

            res = self.get_rules()

            worksheet.write(row, 0, 'Employee', cell_text_format)
            worksheet.write(row, 1, 'Department', cell_text_format)
            worksheet.write(row, 2, 'Job Title', cell_text_format)
            worksheet.write(row, 3, 'Employee Bank', cell_text_format)
            worksheet.write(row, 4, 'Account Number', cell_text_format)
            worksheet.write(row, 5, 'Payslip Ref', cell_text_format)

            row_set = row
            col = 6

            for vals in res:
                worksheet.write(row, col, vals[0], cell_text_format)
                col += 1

            row += 1
            payslip_ids = self.env['hr.payslip'].search([
                ('date_from', '=', self.from_date),
                ('date_to', '=', self.date_end),
                ('state', '=', 'draft')
            ])
            colm = 6

            for payslip in payslip_ids:
                emp = payslip.employee_id
                worksheet.write(row, 0, emp.name or '', cell_text_format_new)
                worksheet.write(row, 1, emp.department_id.name or '', cell_text_format_new)
                worksheet.write(row, 2, emp.job_id.name or '', cell_text_format_new)
                worksheet.write(row, 3, emp.bank_account_id.bank_id.name or '', cell_text_format_new)
                worksheet.write(row, 4, emp.bank_account_id.acc_number or '', cell_text_format_new)
                worksheet.write(row, 5, payslip.number or '', cell_text_format_new)

                col = colm
                for vals in res:
                    amount = 0
                    for line in payslip.line_ids:
                        if line.code == vals[1]:
                            amount = line.total
                            break
                    worksheet.write(row, col, amount, cell_number_format)
                    col += 1
                row += 1

            worksheet.write(row, 0, 'Grand Total', cell_text_format)
            for i in range(colm, col):
                cell1 = xl_rowcol_to_cell(row_set + 1, i)
                cell2 = xl_rowcol_to_cell(row - 1, i)
                worksheet.write_formula(row, i, f'SUM({cell1}:{cell2})', normal_num_bold)

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)
        attachment = self.env['ir.attachment'].create({
            'name': 'Payroll',
            'datas': file_download,
            'store_fname': 'payroll.xlsx',
            'res_model': 'payroll.report.wiz',
            'res_id': self.id
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=ir.attachment&id={attachment.id}&filename=payroll.xlsx&field=datas&download=true&filename=payroll.xlsx",
            'target': 'self',
        }


class PayrollReportExcel(models.TransientModel):
    _name = 'payroll.report.excel'
    _description = 'Payroll Excel File'

    name = fields.Char('File Name', readonly=True)
    file_download = fields.Binary('Download payroll', readonly=True)
