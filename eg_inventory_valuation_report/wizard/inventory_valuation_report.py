import base64
from io import BytesIO
import xlwt
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class InventoryValuationReport(models.TransientModel):
    _name = 'inventory.valuation.report'
    _description = 'Inventory Valuation Report'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    file_name = fields.Char(string='File Name')
    data = fields.Binary('Download Report', readonly=True)
    group_by_category = fields.Boolean(string='Group by Category', default=True)
    filter_by = fields.Selection([
        ('product', 'Product'),
        ('category', 'Category')
    ], string='Filter By', default='product')
    warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouses')
    location_ids = fields.Many2many('stock.location', string='Locations')
    company_id = fields.Many2one('res.company', string='Company')

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date > record.end_date:
                raise ValidationError(_("End date must be greater than or equal to Start date."))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.warehouse_ids = False
        self.location_ids = False

    def action_pdf_report(self):
        report_data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'company_name': self.env.user.company_id.name,
            'company_street': self.env.user.company_id.street,
            'company_city': self.env.user.company_id.city,
            'company_zip': self.env.user.company_id.zip,
            'company_country': self.env.user.company_id.country_id.name if self.env.user.company_id.country_id else '',
            'filter_by': self.filter_by,
            'warehouses': [],
        }
        report_data['warehouses'] = []
        warehouse_ids = self.warehouse_ids or self.env['stock.warehouse'].search([])
        location_ids = self.location_ids
        
        for warehouse_id in warehouse_ids:
            products, totals = self._get_product_data(warehouse_id, location_ids)
            warehouse_data = {
                'warehouse_name': warehouse_id.name,
                'products': products,
                'totals': totals
            }
            report_data['warehouses'].append(warehouse_data)
        
        # Handle locations if specified
        if location_ids:
            for location_id in location_ids:
                products, totals = self._get_product_data_for_location(location_id)
                warehouse_data = {
                    'warehouse_name': location_id.name,
                    'products': products,
                    'totals': totals
                }
                report_data['warehouses'].append(warehouse_data)
        
        report_action = self.env.ref('eg_inventory_valuation_report.stock_inventory_pdf_report_report')
        return report_action.report_action(self, data=report_data)

    def action_xls_report(self):
        output = BytesIO()
        workbook = xlwt.Workbook()
        warehouse_ids = self.warehouse_ids or self.env['stock.warehouse'].search([])
        location_ids = self.location_ids
        
        for warehouse_id in warehouse_ids:
            products, totals = self._get_product_data(warehouse_id, location_ids)
            sheet = workbook.add_sheet(f"Inventory Valuation Report - {warehouse_id.name}")
            sheet.col(0).width = int(33 * 260)
            sheet.col(1).width = int(20 * 260)
            sheet.col(2).width = int(17 * 260)
            sheet.col(3).width = int(15 * 260)
            sheet.col(4).width = int(10 * 260)
            sheet.col(5).width = int(10 * 260)
            sheet.col(6).width = int(10 * 260)
            sheet.col(7).width = int(10 * 260)
            sheet.col(8).width = int(21 * 260)
            sheet.col(9).width = int(15 * 260)
            sheet.col(10).width = int(16 * 260)
            sheet.col(11).width = int(17 * 260)
            sheet.col(12).width = int(17 * 260)
            sheet.col(13).width = int(17 * 260)

            sheet.row(0).height = 150 * 4
            sheet.row(1).height = 150 * 3
            sheet.row(2).height = 150 * 3
            for i in range(3, 10):
                sheet.row(i).height = 150 * 2

            header_style = xlwt.easyxf(
                'font:height 500,bold True;pattern: pattern solid, fore_colour ice_blue ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                'left thin, right thin, top thin, bottom thin;'
            )
            chanes_style = xlwt.easyxf(
                'font:height 270,bold True;pattern: pattern solid, fore_colour white ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                'left thin, right thin, top thin, bottom thin;'
            )
            total_style = xlwt.easyxf(
                'font:height 230,bold True;pattern: pattern solid, fore_colour ice_blue ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                'left thin, right thin, top thin, bottom thin;'
            )
            text_style = xlwt.easyxf(
                'font:bold True;pattern: pattern solid, fore_colour white ;align: horiz center; '
                'borders: top_color black, bottom_color black, right_color black, left_color black, left thin, right thin, '
                'top thin, bottom thin;'
            )

            sheet.write_merge(0, 0, 0, 13, f"Stock Inventory Valuation Report - {warehouse_id.name}", header_style)
            sheet.write_merge(1, 1, 0, 13,
                              f"Company:{self.company_id.name}",
                              chanes_style)
            sheet.write_merge(2, 2, 0, 13, f"{self.start_date} To {self.end_date}", chanes_style)

            sheet.write(3, 0, 'Products', chanes_style)
            sheet.write_merge(3, 3, 1, 1, 'Costing Methods', chanes_style)
            sheet.write_merge(3, 3, 2, 3, 'Beginning', chanes_style)
            sheet.write_merge(4, 4, 2, 2, 'Qty', text_style)
            sheet.write_merge(4, 4, 3, 3, 'Value', text_style)
            sheet.write_merge(3, 3, 4, 5, 'Received', chanes_style)
            sheet.write_merge(4, 4, 4, 4, 'Qty', text_style)
            sheet.write_merge(4, 4, 5, 5, 'Value', text_style)
            sheet.write_merge(3, 3, 6, 7, 'Sales', chanes_style)
            sheet.write_merge(4, 4, 6, 6, 'Qty', text_style)
            sheet.write_merge(4, 4, 7, 7, 'Value', text_style)
            sheet.write_merge(3, 3, 8, 9, 'Internal', chanes_style)
            sheet.write_merge(4, 4, 8, 8, 'Qty', text_style)
            sheet.write_merge(4, 4, 9, 9, 'Value', text_style)
            sheet.write_merge(3, 3, 10, 11, 'Adjustment', chanes_style)
            sheet.write_merge(4, 4, 10, 10, 'Qty', text_style)
            sheet.write_merge(4, 4, 11, 11, 'Value', text_style)
            sheet.write_merge(3, 3, 12, 13, 'Ending', chanes_style)
            sheet.write_merge(4, 4, 12, 12, 'Qty', text_style)
            sheet.write_merge(4, 4, 13, 13, 'Value', text_style)

            row = 5
            warehouse_totals = {
                'beginning_qty': 0,
                'beginning_value': 0,
                'received_qty': 0,
                'received_value': 0,
                'sales_qty': 0,
                'sales_value': 0,
                'internal_qty': 0,
                'internal_value': 0,
                'adjustment_qty': 0,
                'adjustment_value': 0,
                'ending_qty': 0,
                'ending_value': 0,
            }

            for product_data in products:
                if self.filter_by == 'category' and 'category_name' in product_data:
                    sheet.write(row, 0, product_data['category_name'], total_style)
                    row += 1
                    for product in product_data['products']:
                        sheet.write(row, 0, product['name'])
                        sheet.write(row, 1, product.get('costing_method', ''))
                        sheet.write(row, 2, product.get('beginning_qty'))
                        sheet.write(row, 3, product.get('beginning_value'))
                        sheet.write(row, 4, product.get('received_qty'))
                        sheet.write(row, 5, product.get('received_value'))
                        sheet.write(row, 6, product.get('sales_qty'))
                        sheet.write(row, 7, product.get('sales_value'))
                        sheet.write(row, 8, product.get('internal_qty'))
                        sheet.write(row, 9, product.get('internal_value'))
                        sheet.write(row, 10, product.get('adjustment_qty'))
                        sheet.write(row, 11, product.get('adjustment_value'))
                        sheet.write(row, 12, product.get('ending_qty'))
                        sheet.write(row, 13, product.get('ending_value'))

                        warehouse_totals['beginning_qty'] += product['beginning_qty']
                        warehouse_totals['beginning_value'] += product['beginning_value']
                        warehouse_totals['received_qty'] += product['received_qty']
                        warehouse_totals['received_value'] += product['received_value']
                        warehouse_totals['sales_qty'] += product['sales_qty']
                        warehouse_totals['sales_value'] += product['sales_value']
                        warehouse_totals['internal_qty'] += product['internal_qty']
                        warehouse_totals['internal_value'] += product['internal_value']
                        warehouse_totals['adjustment_qty'] += product['adjustment_qty']
                        warehouse_totals['adjustment_value'] += product['adjustment_value']
                        warehouse_totals['ending_qty'] += product['ending_qty']
                        warehouse_totals['ending_value'] += product['ending_value']

                        row += 1
                elif self.filter_by == 'product':
                    sheet.write(row, 0, product_data['name'])
                    sheet.write(row, 1, product_data.get('costing_method', ''))
                    sheet.write(row, 2, product_data.get('beginning_qty'))
                    sheet.write(row, 3, product_data.get('beginning_value'))
                    sheet.write(row, 4, product_data.get('received_qty'))
                    sheet.write(row, 5, product_data.get('received_value'))
                    sheet.write(row, 6, product_data.get('sales_qty'))
                    sheet.write(row, 7, product_data.get('sales_value'))
                    sheet.write(row, 8, product_data.get('internal_qty'))
                    sheet.write(row, 9, product_data.get('internal_value'))
                    sheet.write(row, 10, product_data.get('adjustment_qty'))
                    sheet.write(row, 11, product_data.get('adjustment_value'))
                    sheet.write(row, 12, product_data.get('ending_qty'))
                    sheet.write(row, 13, product_data.get('ending_value'))

                    warehouse_totals['beginning_qty'] += product_data['beginning_qty']
                    warehouse_totals['beginning_value'] += product_data['beginning_value']
                    warehouse_totals['received_qty'] += product_data['received_qty']
                    warehouse_totals['received_value'] += product_data['received_value']
                    warehouse_totals['sales_qty'] += product_data['sales_qty']
                    warehouse_totals['sales_value'] += product_data['sales_value']
                    warehouse_totals['internal_qty'] += product_data['internal_qty']
                    warehouse_totals['internal_value'] += product_data['internal_value']
                    warehouse_totals['adjustment_qty'] += product_data['adjustment_qty']
                    warehouse_totals['adjustment_value'] += product_data['adjustment_value']
                    warehouse_totals['ending_qty'] += product_data['ending_qty']
                    warehouse_totals['ending_value'] += product_data['ending_value']

                    row += 1

            sheet.write(row, 0, 'Total', total_style)
            sheet.write(row, 2, warehouse_totals['beginning_qty'])
            sheet.write(row, 3, warehouse_totals['beginning_value'])
            sheet.write(row, 4, warehouse_totals['received_qty'])
            sheet.write(row, 5, warehouse_totals['received_value'])
            sheet.write(row, 6, warehouse_totals['sales_qty'])
            sheet.write(row, 7, warehouse_totals['sales_value'])
            sheet.write(row, 8, warehouse_totals['internal_qty'])
            sheet.write(row, 9, warehouse_totals['internal_value'])
            sheet.write(row, 10, warehouse_totals['adjustment_qty'])
            sheet.write(row, 11, warehouse_totals['adjustment_value'])
            sheet.write(row, 12, warehouse_totals['ending_qty'])
            sheet.write(row, 13, warehouse_totals['ending_value'])
        
        # Process locations if specified
        if location_ids:
            for location_id in location_ids:
                products, totals = self._get_product_data_for_location(location_id)
                sheet = workbook.add_sheet(f"Inventory Valuation Report - {location_id.name}")
                sheet.col(0).width = int(33 * 260)
                sheet.col(1).width = int(20 * 260)
                sheet.col(2).width = int(17 * 260)
                sheet.col(3).width = int(15 * 260)
                sheet.col(4).width = int(10 * 260)
                sheet.col(5).width = int(10 * 260)
                sheet.col(6).width = int(10 * 260)
                sheet.col(7).width = int(10 * 260)
                sheet.col(8).width = int(21 * 260)
                sheet.col(9).width = int(15 * 260)
                sheet.col(10).width = int(16 * 260)
                sheet.col(11).width = int(17 * 260)
                sheet.col(12).width = int(17 * 260)
                sheet.col(13).width = int(17 * 260)

                sheet.row(0).height = 150 * 4
                sheet.row(1).height = 150 * 3
                sheet.row(2).height = 150 * 3
                for i in range(3, 10):
                    sheet.row(i).height = 150 * 2

                header_style = xlwt.easyxf(
                    'font:height 500,bold True;pattern: pattern solid, fore_colour ice_blue ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                    'left thin, right thin, top thin, bottom thin;'
                )
                chanes_style = xlwt.easyxf(
                    'font:height 270,bold True;pattern: pattern solid, fore_colour white ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                    'left thin, right thin, top thin, bottom thin;'
                )
                total_style = xlwt.easyxf(
                    'font:height 230,bold True;pattern: pattern solid, fore_colour ice_blue ;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black, '
                    'left thin, right thin, top thin, bottom thin;'
                )
                text_style = xlwt.easyxf(
                    'font:bold True;pattern: pattern solid, fore_colour white ;align: horiz center; '
                    'borders: top_color black, bottom_color black, right_color black, left_color black, left thin, right thin, '
                    'top thin, bottom thin;'
                )

                sheet.write_merge(0, 0, 0, 13, f"Stock Inventory Valuation Report - {location_id.name}", header_style)
                sheet.write_merge(1, 1, 0, 13,
                                  f"Company:{self.company_id.name}",
                                  chanes_style)
                sheet.write_merge(2, 2, 0, 13, f"{self.start_date} To {self.end_date}", chanes_style)

                sheet.write(3, 0, 'Products', chanes_style)
                sheet.write_merge(3, 3, 1, 1, 'Costing Methods', chanes_style)
                sheet.write_merge(3, 3, 2, 3, 'Beginning', chanes_style)
                sheet.write_merge(4, 4, 2, 2, 'Qty', text_style)
                sheet.write_merge(4, 4, 3, 3, 'Value', text_style)
                sheet.write_merge(3, 3, 4, 5, 'Received', chanes_style)
                sheet.write_merge(4, 4, 4, 4, 'Qty', text_style)
                sheet.write_merge(4, 4, 5, 5, 'Value', text_style)
                sheet.write_merge(3, 3, 6, 7, 'Sales', chanes_style)
                sheet.write_merge(4, 4, 6, 6, 'Qty', text_style)
                sheet.write_merge(4, 4, 7, 7, 'Value', text_style)
                sheet.write_merge(3, 3, 8, 9, 'Internal', chanes_style)
                sheet.write_merge(4, 4, 8, 8, 'Qty', text_style)
                sheet.write_merge(4, 4, 9, 9, 'Value', text_style)
                sheet.write_merge(3, 3, 10, 11, 'Adjustment', chanes_style)
                sheet.write_merge(4, 4, 10, 10, 'Qty', text_style)
                sheet.write_merge(4, 4, 11, 11, 'Value', text_style)
                sheet.write_merge(3, 3, 12, 13, 'Ending', chanes_style)
                sheet.write_merge(4, 4, 12, 12, 'Qty', text_style)
                sheet.write_merge(4, 4, 13, 13, 'Value', text_style)

                row = 5
                location_totals = {
                    'beginning_qty': 0,
                    'beginning_value': 0,
                    'received_qty': 0,
                    'received_value': 0,
                    'sales_qty': 0,
                    'sales_value': 0,
                    'internal_qty': 0,
                    'internal_value': 0,
                    'adjustment_qty': 0,
                    'adjustment_value': 0,
                    'ending_qty': 0,
                    'ending_value': 0,
                }

                for product_data in products:
                    if self.filter_by == 'category' and 'category_name' in product_data:
                        sheet.write(row, 0, product_data['category_name'], total_style)
                        row += 1
                        for product in product_data['products']:
                            sheet.write(row, 0, product['name'])
                            sheet.write(row, 1, product.get('costing_method', ''))
                            sheet.write(row, 2, product.get('beginning_qty'))
                            sheet.write(row, 3, product.get('beginning_value'))
                            sheet.write(row, 4, product.get('received_qty'))
                            sheet.write(row, 5, product.get('received_value'))
                            sheet.write(row, 6, product.get('sales_qty'))
                            sheet.write(row, 7, product.get('sales_value'))
                            sheet.write(row, 8, product.get('internal_qty'))
                            sheet.write(row, 9, product.get('internal_value'))
                            sheet.write(row, 10, product.get('adjustment_qty'))
                            sheet.write(row, 11, product.get('adjustment_value'))
                            sheet.write(row, 12, product.get('ending_qty'))
                            sheet.write(row, 13, product.get('ending_value'))

                            location_totals['beginning_qty'] += product['beginning_qty']
                            location_totals['beginning_value'] += product['beginning_value']
                            location_totals['received_qty'] += product['received_qty']
                            location_totals['received_value'] += product['received_value']
                            location_totals['sales_qty'] += product['sales_qty']
                            location_totals['sales_value'] += product['sales_value']
                            location_totals['internal_qty'] += product['internal_qty']
                            location_totals['internal_value'] += product['internal_value']
                            location_totals['adjustment_qty'] += product['adjustment_qty']
                            location_totals['adjustment_value'] += product['adjustment_value']
                            location_totals['ending_qty'] += product['ending_qty']
                            location_totals['ending_value'] += product['ending_value']

                            row += 1
                    elif self.filter_by == 'product':
                        sheet.write(row, 0, product_data['name'])
                        sheet.write(row, 1, product_data.get('costing_method', ''))
                        sheet.write(row, 2, product_data.get('beginning_qty'))
                        sheet.write(row, 3, product_data.get('beginning_value'))
                        sheet.write(row, 4, product_data.get('received_qty'))
                        sheet.write(row, 5, product_data.get('received_value'))
                        sheet.write(row, 6, product_data.get('sales_qty'))
                        sheet.write(row, 7, product_data.get('sales_value'))
                        sheet.write(row, 8, product_data.get('internal_qty'))
                        sheet.write(row, 9, product_data.get('internal_value'))
                        sheet.write(row, 10, product_data.get('adjustment_qty'))
                        sheet.write(row, 11, product_data.get('adjustment_value'))
                        sheet.write(row, 12, product_data.get('ending_qty'))
                        sheet.write(row, 13, product_data.get('ending_value'))

                        location_totals['beginning_qty'] += product_data['beginning_qty']
                        location_totals['beginning_value'] += product_data['beginning_value']
                        location_totals['received_qty'] += product_data['received_qty']
                        location_totals['received_value'] += product_data['received_value']
                        location_totals['sales_qty'] += product_data['sales_qty']
                        location_totals['sales_value'] += product_data['sales_value']
                        location_totals['internal_qty'] += product_data['internal_qty']
                        location_totals['internal_value'] += product_data['internal_value']
                        location_totals['adjustment_qty'] += product_data['adjustment_qty']
                        location_totals['adjustment_value'] += product_data['adjustment_value']
                        location_totals['ending_qty'] += product_data['ending_qty']
                        location_totals['ending_value'] += product_data['ending_value']

                        row += 1

                sheet.write(row, 0, 'Total', total_style)
                sheet.write(row, 2, location_totals['beginning_qty'])
                sheet.write(row, 3, location_totals['beginning_value'])
                sheet.write(row, 4, location_totals['received_qty'])
                sheet.write(row, 5, location_totals['received_value'])
                sheet.write(row, 6, location_totals['sales_qty'])
                sheet.write(row, 7, location_totals['sales_value'])
                sheet.write(row, 8, location_totals['internal_qty'])
                sheet.write(row, 9, location_totals['internal_value'])
                sheet.write(row, 10, location_totals['adjustment_qty'])
                sheet.write(row, 11, location_totals['adjustment_value'])
                sheet.write(row, 12, location_totals['ending_qty'])
                sheet.write(row, 13, location_totals['ending_value'])

        workbook.save(output)
        file_data = base64.b64encode(output.getvalue())
        output.close()

        self.write({
            'file_name': 'inventory_valuation_report.xls',
            'data': file_data,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=inventory.valuation.report&id=%d&field=data&download=true&filename=%s' % (
                self.id, 'stock_inventory_report.xls'),
            'target': 'self',
        }

    def _get_product_beginning_qty(self, product_id, warehouse_id):
        qty_available = 0
        custom_domain = []
        if self.company_id:
            custom_domain.append(('company_id', '=', self.company_id.id))
        if warehouse_id:
            location_ids = warehouse_id.view_location_id.ids + warehouse_id.view_location_id.child_ids.ids
            custom_domain.append(('location_id', 'in', location_ids))
        domain_quant = [('product_id', 'in', product_id.ids)
                        ] + custom_domain
        domain_move_in = [('product_id', 'in', product_id.ids), ('state', '=', 'done'),
                          ('location_dest_id', 'in', location_ids)]
        domain_move_out = [('product_id', 'in', product_id.ids), ('state', '=', 'done')
                           ] + custom_domain
        domain_move_in_done = list(domain_move_in)
        domain_move_out_done = list(domain_move_out)
        if self.start_date:
            domain_move_in_done += [('date', '>=', self.start_date)]
            domain_move_out_done += [('date', '>=', self.start_date)]
        if self.end_date:
            domain_move_in_done += [('date', '<=', self.end_date)]
            domain_move_out_done += [('date', '<=', self.end_date)]
        move_line_ids = self.env['stock.move.line']
        quant_ids = self.env['stock.quant']
        quants_data = dict((item['product_id'][0], item['quantity']) for item in quant_ids.read_group(
            domain_quant, ['product_id', 'quantity'], ['product_id']))

        incoming_move_data = dict((item['product_id'][0], item['quantity']) for item in move_line_ids.read_group(
            domain_move_in_done, ['product_id', 'quantity'], ['product_id']))
        outgoing_move_data = dict((item['product_id'][0], item['quantity']) for item in move_line_ids.read_group(
            domain_move_out_done, ['product_id', 'quantity'], ['product_id']))

        for product in product_id.with_context(prefetch_fields=False):
            product_id = product.id
            qty_available = quants_data.get(product_id, 0.0) - incoming_move_data.get(
                product_id, 0.0) + outgoing_move_data.get(product_id, 0.0)

        return qty_available

    def _get_product_purchase_qty(self, product_id, warehouse_id):
        if warehouse_id:
            location_ids = warehouse_id.view_location_id.ids + warehouse_id.view_location_id.child_ids.ids
        received_qty = 0
        purchase_orders = self.env['purchase.order'].search([
            ('date_order', '<=', self.end_date),
            ('date_order', '>=', self.start_date),
            ('state', 'in', ['purchase', 'done']),
        ])
        for order_id in purchase_orders:
            for line_id in order_id.order_line:
                if line_id.product_id.id == product_id.id:
                    stock_moves = self.env['stock.move'].search([
                        ('purchase_line_id', '=', line_id.id),
                        ('state', 'in', ['done']),
                        ('location_dest_id', 'in', location_ids)
                    ])
                    for move_id in stock_moves:
                        received_qty += move_id.quantity

        return received_qty

    def _get_product_sales_qty(self, product_id, warehouse_id):
        sales_qty = sum(line_id.product_uom_qty for line_id in self.env['sale.order.line'].search([
            ('product_id', '=', product_id.id),
            ('order_id.date_order', '<=', self.end_date),
            ('order_id.date_order', '>=', self.start_date),
            ('order_id.warehouse_id', '=', warehouse_id.id)
        ]))
        return sales_qty

    def _get_product_internal_in_qty(self, product_id, warehouse_id):
        internal_in_qty = sum(move_id.product_uom_qty for move_id in self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', 'in', ['done']),
            ('date', '<=', self.end_date),
            ('date', '>=', self.start_date),
            ('picking_type_id.code', '=', 'internal'),
            ('location_dest_id.usage', '=', 'internal'),
            ('location_dest_id.warehouse_id', '=', warehouse_id.id)
        ]))
        return internal_in_qty

    def _get_product_internal_out_qty(self, product_id, warehouse_id):
        internal_out_qty = sum(move_id.product_uom_qty for move_id in self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', 'in', ['done']),
            ('date', '<=', self.end_date),
            ('date', '>=', self.start_date),
            ('picking_type_id.code', '=', 'internal'),
            ('location_id.usage', '=', 'internal'),
            ('location_id.warehouse_id', '=', warehouse_id.id)
        ]))
        return internal_out_qty

    def _get_product_adjustment_qty(self, product_id, warehouse_id):
        adjustment_qty = 0
        adjustment_move_ids = self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', '=', 'done'),
            ('date', '<=', self.end_date),
            ('is_inventory', '=', True),
        ])

        for move_id in adjustment_move_ids:
            if move_id.location_id.usage == 'inventory':
                adjustment_qty += move_id.quantity
            elif move_id.location_dest_id.usage == 'inventory':
                adjustment_qty -= move_id.quantity

        return adjustment_qty

    def _get_product_ending_qty(self, product_id, warehouse_id):
        beginning_qty = self._get_product_beginning_qty(product_id, warehouse_id)
        received_qty = self._get_product_purchase_qty(product_id, warehouse_id)
        sales_qty = self._get_product_sales_qty(product_id, warehouse_id)
        internal_in_qty = self._get_product_internal_in_qty(product_id, warehouse_id)
        internal_out_qty = self._get_product_internal_out_qty(product_id, warehouse_id)
        adjustment_qty = self._get_product_adjustment_qty(product_id, warehouse_id)
        ending_qty = beginning_qty + received_qty - sales_qty + internal_in_qty - internal_out_qty + \
                     + adjustment_qty
        return ending_qty

    def update_totals(self, totals, data):
        for key in totals:
            totals[key] += data.get(key, 0)

    def _get_product_data(self, warehouse_id, location_ids=None):
        products = []
        totals = {
            'beginning_qty': 0,
            'beginning_value': 0,
            'received_qty': 0,
            'received_value': 0,
            'sales_qty': 0,
            'sales_value': 0,
            'internal_qty': 0,
            'internal_value': 0,
            'adjustment_qty': 0,
            'adjustment_value': 0,
            'ending_qty': 0,
            'ending_value': 0,
        }

        domain = [('create_date', '>=', self.start_date), ('create_date', '<=', self.end_date)]

        if self.filter_by == 'category':
            self.filter_by_category(warehouse_id, totals, products)
        elif self.filter_by == 'product':
            self.filter_by_product(warehouse_id, domain, totals, products)

        return products, totals

    def get_product_data(self, product_id, warehouse_id):
        beginning_qty = self._get_product_beginning_qty(product_id, warehouse_id)
        received_qty = self._get_product_purchase_qty(product_id, warehouse_id)
        sales_qty = self._get_product_sales_qty(product_id, warehouse_id)
        internal_in_qty = self._get_product_internal_in_qty(product_id, warehouse_id)
        internal_out_qty = self._get_product_internal_out_qty(product_id, warehouse_id)
        adjustment_qty = self._get_product_adjustment_qty(product_id, warehouse_id)

        ending_qty = beginning_qty + received_qty - sales_qty + internal_in_qty - internal_out_qty + adjustment_qty

        return {
            'name': product_id.name,
            'costing_method': product_id.categ_id.property_cost_method,
            'beginning_qty': beginning_qty,
            'beginning_value': beginning_qty * product_id.standard_price,
            'received_qty': received_qty,
            'received_value': received_qty * product_id.standard_price,
            'sales_qty': sales_qty,
            'sales_value': sales_qty * product_id.standard_price,
            'internal_qty': internal_in_qty - internal_out_qty,
            'internal_value': (internal_in_qty - internal_out_qty) * product_id.standard_price,
            'adjustment_qty': adjustment_qty,
            'adjustment_value': adjustment_qty * product_id.standard_price,
            'ending_qty': ending_qty,
            'ending_value': ending_qty * product_id.standard_price,
        }

    def filter_by_product(self, warehouse_id, domain, totals, products):
        product_ids = self.env['product.product']
        location_ids = warehouse_id.lot_stock_id + warehouse_id.lot_stock_id.child_ids
        quant_ids = self.env['stock.quant'].search([
            ('location_id', 'in', location_ids.ids)
        ])
        if quant_ids:
            product_ids = quant_ids.mapped('product_id')
        for product_id in product_ids:
            total_qty = self._get_product_ending_qty(product_id, warehouse_id)
            if total_qty > 0:
                product_data = self.get_product_data(product_id, warehouse_id)
                products.append(product_data)
                self.update_totals(totals, product_data)

    def filter_by_category(self, warehouse_id, totals, products):
        product_ids = self.env['product.product']
        location_ids = warehouse_id.lot_stock_id + warehouse_id.lot_stock_id.child_ids
        quant_ids = self.env['stock.quant'].search([
            ('location_id', 'in', location_ids.ids)
        ])
        if quant_ids:
            product_ids = quant_ids.mapped('product_id')
        category_ids = self.env['product.category'].search([])
        for category_id in category_ids:
            category_totals = {key: 0 for key in ['beginning_qty', 'beginning_value', 'received_qty', 'received_value',
                                                  'sales_qty', 'sales_value', 'internal_qty',
                                                  'internal_value', 'adjustment_qty', 'adjustment_value', 'ending_qty',
                                                  'ending_value']}
            category_data = []
            products_in_category = self.env['product.product'].search(
                [('categ_id', '=', category_id.id), ('id', 'in', product_ids.ids)])
            for product_id in products_in_category:
                total_qty = self._get_product_ending_qty(product_id, warehouse_id)
                if total_qty > 0:
                    product_data = self.get_product_data(product_id, warehouse_id)
                    category_data.append(product_data)
                    self.update_totals(category_totals, product_data)
            if category_data:
                products.append({
                    'category_name': category_id.name,
                    'products': category_data,
                    'category_totals': category_totals,
                })
                self.update_totals(totals, category_totals)
    def _get_product_data_for_location(self, location_id):
        products = []
        totals = {
            'beginning_qty': 0,
            'beginning_value': 0,
            'received_qty': 0,
            'received_value': 0,
            'sales_qty': 0,
            'sales_value': 0,
            'internal_qty': 0,
            'internal_value': 0,
            'adjustment_qty': 0,
            'adjustment_value': 0,
            'ending_qty': 0,
            'ending_value': 0,
        }

        domain = [('create_date', '>=', self.start_date), ('create_date', '<=', self.end_date)]

        if self.filter_by == 'category':
            self.filter_by_category_location(location_id, totals, products)
        elif self.filter_by == 'product':
            self.filter_by_product_location(location_id, domain, totals, products)

        return products, totals

    def filter_by_product_location(self, location_id, domain, totals, products):
        product_ids = self.env['product.product']
        quant_ids = self.env['stock.quant'].search([
            ('location_id', '=', location_id.id)
        ])
        if quant_ids:
            product_ids = quant_ids.mapped('product_id')
        for product_id in product_ids:
            total_qty = self._get_product_ending_qty_location(product_id, location_id)
            if total_qty > 0:
                product_data = self.get_product_data_location(product_id, location_id)
                products.append(product_data)
                self.update_totals(totals, product_data)

    def filter_by_category_location(self, location_id, totals, products):
        product_ids = self.env['product.product']
        quant_ids = self.env['stock.quant'].search([
            ('location_id', '=', location_id.id)
        ])
        if quant_ids:
            product_ids = quant_ids.mapped('product_id')
        category_ids = self.env['product.category'].search([])
        for category_id in category_ids:
            category_totals = {key: 0 for key in ['beginning_qty', 'beginning_value', 'received_qty', 'received_value',
                                                  'sales_qty', 'sales_value', 'internal_qty',
                                                  'internal_value', 'adjustment_qty', 'adjustment_value', 'ending_qty',
                                                  'ending_value']}
            category_data = []
            products_in_category = self.env['product.product'].search(
                [('categ_id', '=', category_id.id), ('id', 'in', product_ids.ids)])
            for product_id in products_in_category:
                total_qty = self._get_product_ending_qty_location(product_id, location_id)
                if total_qty > 0:
                    product_data = self.get_product_data_location(product_id, location_id)
                    category_data.append(product_data)
                    self.update_totals(category_totals, product_data)
            if category_data:
                products.append({
                    'category_name': category_id.name,
                    'products': category_data,
                    'category_totals': category_totals,
                })
                self.update_totals(totals, category_totals)

    def get_product_data_location(self, product_id, location_id):
        beginning_qty = self._get_product_beginning_qty_location(product_id, location_id)
        received_qty = self._get_product_purchase_qty_location(product_id, location_id)
        sales_qty = self._get_product_sales_qty_location(product_id, location_id)
        internal_in_qty = self._get_product_internal_in_qty_location(product_id, location_id)
        internal_out_qty = self._get_product_internal_out_qty_location(product_id, location_id)
        adjustment_qty = self._get_product_adjustment_qty_location(product_id, location_id)

        ending_qty = beginning_qty + received_qty - sales_qty + internal_in_qty - internal_out_qty + adjustment_qty

        return {
            'name': product_id.name,
            'costing_method': product_id.categ_id.property_cost_method,
            'beginning_qty': beginning_qty,
            'beginning_value': beginning_qty * product_id.standard_price,
            'received_qty': received_qty,
            'received_value': received_qty * product_id.standard_price,
            'sales_qty': sales_qty,
            'sales_value': sales_qty * product_id.standard_price,
            'internal_qty': internal_in_qty - internal_out_qty,
            'internal_value': (internal_in_qty - internal_out_qty) * product_id.standard_price,
            'adjustment_qty': adjustment_qty,
            'adjustment_value': adjustment_qty * product_id.standard_price,
            'ending_qty': ending_qty,
            'ending_value': ending_qty * product_id.standard_price,
        }

    def _get_product_beginning_qty_location(self, product_id, location_id):
        qty_available = 0
        custom_domain = []
        if self.company_id:
            custom_domain.append(('company_id', '=', self.company_id.id))
        
        domain_quant = [('product_id', '=', product_id.id),
                        ('location_id', '=', location_id.id)] + custom_domain
        
        domain_move_in = [('product_id', '=', product_id.id), ('state', '=', 'done'),
                          ('location_dest_id', '=', location_id.id)]
        domain_move_out = [('product_id', '=', product_id.id), ('state', '=', 'done'),
                           ('location_id', '=', location_id.id)]
        
        domain_move_in_done = list(domain_move_in)
        domain_move_out_done = list(domain_move_out)
        
        if self.start_date:
            domain_move_in_done += [('date', '>=', self.start_date)]
            domain_move_out_done += [('date', '>=', self.start_date)]
        if self.end_date:
            domain_move_in_done += [('date', '<=', self.end_date)]
            domain_move_out_done += [('date', '<=', self.end_date)]
        
        move_line_ids = self.env['stock.move.line']
        quant_ids = self.env['stock.quant']
        
        quants_data = dict((item['product_id'][0], item['quantity']) for item in quant_ids.read_group(
            domain_quant, ['product_id', 'quantity'], ['product_id']) if quant_ids.read_group(
            domain_quant, ['product_id', 'quantity'], ['product_id']))

        incoming_move_data = dict((item['product_id'][0], item['quantity']) for item in move_line_ids.read_group(
            domain_move_in_done, ['product_id', 'quantity'], ['product_id']) if move_line_ids.read_group(
            domain_move_in_done, ['product_id', 'quantity'], ['product_id']))
        
        outgoing_move_data = dict((item['product_id'][0], item['quantity']) for item in move_line_ids.read_group(
            domain_move_out_done, ['product_id', 'quantity'], ['product_id']) if move_line_ids.read_group(
            domain_move_out_done, ['product_id', 'quantity'], ['product_id']))

        qty_available = quants_data.get(product_id.id, 0.0) - incoming_move_data.get(
            product_id.id, 0.0) + outgoing_move_data.get(product_id.id, 0.0)

        return qty_available

    def _get_product_purchase_qty_location(self, product_id, location_id):
        received_qty = 0
        purchase_orders = self.env['purchase.order'].search([
            ('date_order', '<=', self.end_date),
            ('date_order', '>=', self.start_date),
            ('state', 'in', ['purchase', 'done']),
        ])
        for order_id in purchase_orders:
            for line_id in order_id.order_line:
                if line_id.product_id.id == product_id.id:
                    stock_moves = self.env['stock.move'].search([
                        ('purchase_line_id', '=', line_id.id),
                        ('state', 'in', ['done']),
                        ('location_dest_id', '=', location_id.id)
                    ])
                    for move_id in stock_moves:
                        received_qty += move_id.quantity

        return received_qty

    def _get_product_sales_qty_location(self, product_id, location_id):
        sales_qty = 0
        stock_moves = self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', '=', 'done'),
            ('location_id', '=', location_id.id),
            ('picking_type_id.code', '=', 'outgoing'),
            ('date', '<=', self.end_date),
            ('date', '>=', self.start_date),
        ])
        for move_id in stock_moves:
            sales_qty += move_id.quantity
        return sales_qty

    def _get_product_internal_in_qty_location(self, product_id, location_id):
        internal_in_qty = sum(move_id.product_uom_qty for move_id in self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', 'in', ['done']),
            ('date', '<=', self.end_date),
            ('date', '>=', self.start_date),
            ('picking_type_id.code', '=', 'internal'),
            ('location_dest_id', '=', location_id.id)
        ]))
        return internal_in_qty

    def _get_product_internal_out_qty_location(self, product_id, location_id):
        internal_out_qty = sum(move_id.product_uom_qty for move_id in self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', 'in', ['done']),
            ('date', '<=', self.end_date),
            ('date', '>=', self.start_date),
            ('picking_type_id.code', '=', 'internal'),
            ('location_id', '=', location_id.id)
        ]))
        return internal_out_qty

    def _get_product_adjustment_qty_location(self, product_id, location_id):
        adjustment_qty = 0
        adjustment_move_ids = self.env['stock.move'].search([
            ('product_id', '=', product_id.id),
            ('state', '=', 'done'),
            ('date', '<=', self.end_date),
            ('is_inventory', '=', True),
        ])

        for move_id in adjustment_move_ids:
            if move_id.location_id.id == location_id.id and move_id.location_id.usage == 'inventory':
                adjustment_qty += move_id.quantity
            elif move_id.location_dest_id.id == location_id.id and move_id.location_dest_id.usage == 'inventory':
                adjustment_qty -= move_id.quantity

        return adjustment_qty

    def _get_product_ending_qty_location(self, product_id, location_id):
        beginning_qty = self._get_product_beginning_qty_location(product_id, location_id)
        received_qty = self._get_product_purchase_qty_location(product_id, location_id)
        sales_qty = self._get_product_sales_qty_location(product_id, location_id)
        internal_in_qty = self._get_product_internal_in_qty_location(product_id, location_id)
        internal_out_qty = self._get_product_internal_out_qty_location(product_id, location_id)
        adjustment_qty = self._get_product_adjustment_qty_location(product_id, location_id)
        ending_qty = beginning_qty + received_qty - sales_qty + internal_in_qty - internal_out_qty + adjustment_qty
        return ending_qty