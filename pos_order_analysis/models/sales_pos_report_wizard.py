import base64
from io import BytesIO

import xlsxwriter

from odoo import fields, models


class SalesPosReportWizard(models.TransientModel):
    _name = 'sales.pos.report.wizard'
    _description = 'Sales & POS Excel Report Wizard'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    report_type = fields.Selection([
        ('sales', 'Sales Order'),
        ('pos', 'POS Order'),
        ('both', 'Both'),
    ], string='Report Type', required=True, default='sales')
    cashier_ids = fields.Many2many('res.users', string='Cashiers', help='Select cashiers to filter POS orders')

    def action_export_excel(self):
        # report_xlsx is not available on 18.0: build the workbook here and
        # hand it to the browser through a temporary attachment.
        self.ensure_one()
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        self._generate_xlsx_report(workbook, {
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'report_type': self.report_type,
            'cashier_ids': self.cashier_ids.ids,
        })
        workbook.close()

        filename = 'Sales_POS_Report_%s.xlsx' % self.start_date.strftime('%Y_%m_%d')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _generate_xlsx_report(self, workbook, data):
        sheet = workbook.add_worksheet('Sales/POS Report')

        # Formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
        bold_wrap = workbook.add_format({'bold': True, 'text_wrap': True, 'bg_color': '#F9F9F9', 'border': 1})
        normal_format = workbook.add_format({'text_wrap': True, 'border': 1})
        subtotal_format = workbook.add_format({'bold': True, 'bg_color': '#EAF1DD', 'border': 1, 'align': 'right'})

        # Set column widths
        sheet.set_column('A:A', 20)  # Order
        sheet.set_column('B:B', 30)  # Customer
        sheet.set_column('C:C', 20)  # Date
        sheet.set_column('D:H', 15)  # Amounts & Quantity & Margin

        # Header info
        start_date = data['start_date']
        end_date = data['end_date']
        report_type = data['report_type']
        cashier_ids = data.get('cashier_ids', [])

        # Report period
        sheet.write('A1', 'Report Period:', header_format)
        sheet.write('B1', f"{start_date} to {end_date}", normal_format)

        # Table headers
        headers = ['Order', 'Customer', 'Date', 'Untaxed Amount', 'Tax Amount', 'Total Amount', 'Quantity', 'Margin']
        for col, h in enumerate(headers):
            sheet.write(3, col, h, header_format)

        row = 4

        def write_lines(orders, is_pos=False):
            nonlocal row
            untaxed_total = tax_total = grand_total = margin_total = quantity_total = 0.0

            for order in orders:
                untaxed = order.amount_untaxed if not is_pos else order.amount_total - order.amount_tax
                tax = order.amount_tax
                total = order.amount_total

                if is_pos:
                    cost = sum(line.price_subtotal for line in order.lines)
                    qty = sum(line.qty for line in order.lines)
                else:
                    cost = sum(line.product_id.standard_price * line.product_uom_qty for line in order.order_line)
                    qty = sum(line.product_uom_qty for line in order.order_line)

                margin = total - cost

                sheet.write(row, 0, order.name or '', normal_format)
                sheet.write(row, 1, order.partner_id.name or '', normal_format)
                sheet.write(row, 2, str(order.date_order) or '', normal_format)
                sheet.write(row, 3, untaxed, normal_format)
                sheet.write(row, 4, tax, normal_format)
                sheet.write(row, 5, total, normal_format)
                sheet.write(row, 6, qty, normal_format)
                sheet.write(row, 7, margin, normal_format)

                untaxed_total += untaxed
                tax_total += tax
                grand_total += total
                margin_total += margin
                quantity_total += qty
                row += 1

            # Subtotal row
            sheet.write(row, 2, 'Subtotal', subtotal_format)
            sheet.write(row, 3, untaxed_total, subtotal_format)
            sheet.write(row, 4, tax_total, subtotal_format)
            sheet.write(row, 5, grand_total, subtotal_format)
            sheet.write(row, 6, quantity_total, subtotal_format)
            sheet.write(row, 7, margin_total, subtotal_format)
            row += 2

        # Grouped Sales Orders
        if report_type in ['sales', 'both']:
            sales_orders = self.env['sale.order'].search([
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date),
                ('state', '=', 'sale'),
            ], order='user_id, date_order')

            grouped_sales = {}
            for order in sales_orders:
                grouped_sales.setdefault(order.user_id.name or 'No Salesperson', []).append(order)

            for salesperson, orders in grouped_sales.items():
                sheet.write(row, 0, f"Salesperson: {salesperson}", bold_wrap)
                row += 1
                write_lines(orders)

        # Grouped POS Orders by POS Config → Cashier
        if report_type in ['pos', 'both']:
            domain = [
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date),
                ('state', '=', 'done'),
            ]
            if cashier_ids:
                domain.append(('user_id', 'in', cashier_ids))

            pos_orders = self.env['pos.order'].search(domain, order='config_id, user_id, date_order')

            grouped_by_config = {}
            for order in pos_orders:
                config_name = order.config_id.name or 'Unnamed POS'
                grouped_by_config.setdefault(config_name, []).append(order)

            for config_name, orders in grouped_by_config.items():
                sheet.write(row, 0, f"POS: {config_name}", bold_wrap)
                row += 1

                grouped_by_cashier = {}
                for order in orders:
                    cashier_name = order.user_id.name or 'No Cashier'
                    grouped_by_cashier.setdefault(cashier_name, []).append(order)

                for cashier_name, cashier_orders in grouped_by_cashier.items():
                    sheet.write(row, 0, f"Cashier: {cashier_name}", normal_format)
                    row += 1
                    write_lines(cashier_orders, is_pos=True)
