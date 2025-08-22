from odoo import models, fields, api
import base64
import io
import xlsxwriter
from datetime import datetime

class PayrollReportWizard(models.TransientModel):
    _name = 'payroll.report.wizard'
    _description = 'Payroll Excel Report Wizard'

    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    end_date = fields.Date(string='End Date', required=True, default=fields.Date.context_today)
    excel_file = fields.Binary(string='Excel File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    def print_report(self):
        self.ensure_one()
        
        # Debug: Print the date range
        print(f"🔍 Payroll Report - Date range: {self.start_date} to {self.end_date}")
        
        # Get payslips with different states for testing
        payslip_obj = self.env['hr.payslip']
        
        # Try different states to see what exists
        domain = [
            ('date_from', '>=', self.start_date),
            ('date_to', '<=', self.end_date),
            ('state', 'in', ['done', 'paid', 'verify'])  # Try multiple states
        ]
        
        payslips = payslip_obj.search(domain)
        
        # Debug: Print found payslips
        print(f"📊 Found {len(payslips)} payslips:")
        for slip in payslips:
            print(f"   - {slip.number}: {slip.employee_id.name}, {slip.date_from} to {slip.date_to}, State: {slip.state}")
        
        # Generate Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Create worksheet
        sheet = workbook.add_worksheet('Payroll Report')
        bold = workbook.add_format({'bold': True})
        header_format = workbook.add_format({
            'bold': True, 
            'bg_color': '#366092', 
            'font_color': 'white', 
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        title_format = workbook.add_format({
            'bold': True, 
            'font_size': 16,
            'align': 'center'
        })
        
        # Set column widths
        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 15)
        sheet.set_column('C:C', 20)
        sheet.set_column('D:D', 15)
        sheet.set_column('E:E', 20)
        sheet.set_column('F:F', 20)
        sheet.set_column('G:G', 15)
        sheet.set_column('H:H', 15)
        sheet.set_column('I:I', 20)
        sheet.set_column('J:J', 15)
        sheet.set_column('K:K', 15)
        sheet.set_column('L:L', 15)
        sheet.set_column('M:M', 15)
        sheet.set_column('N:N', 15)
        sheet.set_column('O:O', 15)
        sheet.set_column('P:P', 15)
        sheet.set_column('Q:Q', 15)
        
        # Report header
        company = self.env.company
        sheet.merge_range('A1:Q1', 'PAYROLL REPORT', title_format)
        sheet.merge_range('A2:Q2', company.name, title_format)
        sheet.merge_range('A3:Q3', f'Period: {self.start_date} to {self.end_date}', title_format)
        
        # Add debug info
        sheet.write('A4', f'Found {len(payslips)} payslips', bold)
        sheet.write('A5', '')  # Empty row for spacing
        
        # Column headers
        headers = [
            'Employee', 'Department', 'Job Title', 'NIDA Number', 
            'Bank Name', 'Account Number', 'TIN Number', 'NSSF Number',
            'Basic Salary', 'Gross Salary', 'Employer NSSF', 'PAYE',
            'Higher Education Loan', 'WCF', 'SDL', 'NHIF Employee', 'Net Salary'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(5, col, header, header_format)
        
        # Data rows
        row = 6
        if payslips:
            for payslip in payslips:
                employee = payslip.employee_id
                
                # Get bank information correctly
                bank_name = ''
                bank_account = ''
                
                # Method 1: Check if employee has bank account linked
                if employee.bank_account_id:
                    bank_name = employee.bank_account_id.bank_id.name or ''
                    bank_account = employee.bank_account_id.acc_number or ''
                
                # Get salary rule values
                basic_salary = self._get_rule_value(payslip, 'BASIC')
                gross_salary = self._get_rule_value(payslip, 'GROSS')
                employer_nssf = self._get_rule_value(payslip, 'NSSF_EMPLOYER')
                paye = self._get_rule_value(payslip, 'PAYE')
                helb = self._get_rule_value(payslip, 'HELB')
                wcf = self._get_rule_value(payslip, 'WCF')
                sdl = self._get_rule_value(payslip, 'SDL')
                nhif = self._get_rule_value(payslip, 'NHIF')
                net_salary = payslip.net_wage
                
                sheet.write(row, 0, employee.name)
                sheet.write(row, 1, employee.department_id.name if employee.department_id else '')
                sheet.write(row, 2, employee.job_id.name if employee.job_id else '')
                sheet.write(row, 3, employee.nida_number or '')
                sheet.write(row, 4, bank_name)  # Fixed: Use correct bank field
                sheet.write(row, 5, bank_account)  # Fixed: Use correct account field
                sheet.write(row, 6, employee.tin_number or '')
                sheet.write(row, 7, employee.nssf_number or '')
                sheet.write(row, 8, basic_salary, money_format)
                sheet.write(row, 9, gross_salary, money_format)
                sheet.write(row, 10, employer_nssf, money_format)
                sheet.write(row, 11, paye, money_format)
                sheet.write(row, 12, helb, money_format)
                sheet.write(row, 13, wcf, money_format)
                sheet.write(row, 14, sdl, money_format)
                sheet.write(row, 15, nhif, money_format)
                sheet.write(row, 16, net_salary, money_format)
                
                row += 1
            
            # Add totals row
            if row > 6:  # Only if there are data rows
                sheet.write(row, 0, 'TOTALS', header_format)
                for col in range(8, 17):
                    sheet.write_formula(row, col, f'=SUM({chr(65+col)}{7}:{chr(65+col)}{row})', money_format)
        else:
            # No payslips found message
            sheet.merge_range('A7:Q7', '❌ NO PAYSLIPS FOUND FOR THE SELECTED PERIOD', header_format)
            sheet.merge_range('A8:Q8', 'Please check:', bold)
            sheet.merge_range('A9:Q9', '- Payslip state (should be "done", "paid", or "verify")')
            sheet.merge_range('A10:Q10', '- Date range matching payslip dates')
            sheet.merge_range('A11:Q11', '- Ensure payslips exist for this period')
        
        workbook.close()
        
        # Save file to wizard and return download action
        excel_file = base64.encodebytes(output.getvalue())
        self.write({
            'excel_file': excel_file,
            'file_name': f'payroll_report_{self.start_date}_to_{self.end_date}.xlsx'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/payroll.report.wizard/{self.id}/excel_file/{self.file_name}?download=true',
            'target': 'self',
        }

    def _get_rule_value(self, payslip, code):
        for line in payslip.line_ids:
            if line.salary_rule_id.code == code:
                return line.total
        return 0.0