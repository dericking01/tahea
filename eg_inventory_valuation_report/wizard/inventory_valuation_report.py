# -*- coding: utf-8 -*-
import base64
from io import BytesIO
import xlwt

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InventoryValuationReport(models.TransientModel):
    _name = 'inventory.valuation.report'
    _description = 'Inventory Valuation Report'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    location_ids = fields.Many2many('stock.location', string='Locations')
    filter_by = fields.Selection([
        ('product', 'Product'),
        ('category', 'Category')
    ], string='Filter By', default='product')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id
    )

    file_name = fields.Char(string='File Name')
    data = fields.Binary('Download Report', readonly=True)

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date > rec.end_date:
                raise ValidationError(_("End date must be after start date."))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.location_ids = False

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------
    def _get_all_locations(self, locations):
        """ Recursively get children locations """
        all_locations = self.env['stock.location']
        for loc in locations:
            all_locations |= loc
            if loc.child_ids:
                all_locations |= self._get_all_locations(loc.child_ids)
        return all_locations

    def _compute_qty(self, product, locations):
        """ Compute movements for product in locations """
        MoveLine = self.env['stock.move.line']
        loc_ids = locations.ids

        move_lines = MoveLine.search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            '|',
            ('location_id', 'in', loc_ids),
            ('location_dest_id', 'in', loc_ids),
        ])

        incoming = outgoing = internal = adjustment = 0.0

        for ml in move_lines:
            # Odoo 18 safety: qty_done may not exist in some builds
            qty = ml.qty_done if hasattr(ml, 'qty_done') else ml.quantity or 0.0

            # Incoming
            if ml.location_id.id not in loc_ids and ml.location_dest_id.id in loc_ids:
                incoming += qty

            # Outgoing
            elif ml.location_id.id in loc_ids and ml.location_dest_id.id not in loc_ids:
                outgoing += qty

            # Internal (net zero)
            elif ml.location_id.id in loc_ids and ml.location_dest_id.id in loc_ids:
                internal += 0

            # Inventory adjustment
            if ml.location_id.usage == 'inventory':
                adjustment -= qty
            if ml.location_dest_id.usage == 'inventory':
                adjustment += qty

        return incoming, outgoing, internal, adjustment

    def _get_product_data(self, product, locations):
        """ Build data line for product """
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', 'in', locations.ids),
            ('company_id', '=', self.company_id.id),
        ])

        beginning_qty = sum(quants.mapped('quantity'))

        received_qty, sales_qty, internal_qty, adjustment_qty = self._compute_qty(product, locations)

        ending_qty = beginning_qty + received_qty - sales_qty + internal_qty + adjustment_qty

        price = product.standard_price

        return {
            'name': product.display_name,
            'costing_method': product.categ_id.property_cost_method,
            'beginning_qty': beginning_qty,
            'beginning_value': beginning_qty * price,
            'received_qty': received_qty,
            'received_value': received_qty * price,
            'sales_qty': sales_qty,
            'sales_value': sales_qty * price,
            'internal_qty': internal_qty,
            'internal_value': internal_qty * price,
            'adjustment_qty': adjustment_qty,
            'adjustment_value': adjustment_qty * price,
            'ending_qty': ending_qty,
            'ending_value': ending_qty * price,
        }

    def _build_dataset(self, location):
        """ Build dataset for one location """
        all_locations = self._get_all_locations(location)

        totals = {
            'beginning_qty': 0, 'beginning_value': 0,
            'received_qty': 0, 'received_value': 0,
            'sales_qty': 0, 'sales_value': 0,
            'internal_qty': 0, 'internal_value': 0,
            'adjustment_qty': 0, 'adjustment_value': 0,
            'ending_qty': 0, 'ending_value': 0,
        }

        products_data = []

        if self.filter_by == 'category':
            categories = self.env['product.category'].search([])

            for cat in categories:
                cat_products = self.env['product.product'].search([('categ_id', '=', cat.id)])
                cat_lines = []
                cat_totals = dict(totals)

                for prod in cat_products:
                    pdata = self._get_product_data(prod, all_locations)
                    if pdata['ending_qty']:
                        cat_lines.append(pdata)
                        for k in totals:
                            cat_totals[k] += pdata[k]

                if cat_lines:
                    products_data.append({
                        'category_name': cat.name,
                        'products': cat_lines,
                        'category_totals': cat_totals,
                    })
                    for k in totals:
                        totals[k] += cat_totals[k]

        else:
            products = self.env['product.product'].search([])

            for prod in products:
                pdata = self._get_product_data(prod, all_locations)
                if pdata['ending_qty']:
                    products_data.append(pdata)
                    for k in totals:
                        totals[k] += pdata[k]

        return products_data, totals

    def get_report_data(self):
        """ Build report """
        report_data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'company': self.company_id,
            'lines': [],
        }

        locations = self.location_ids or self.env['stock.location'].search([('usage', '=', 'internal')])

        for loc in locations:
            products, totals = self._build_dataset(loc)
            report_data['lines'].append({
                'location_name': loc.complete_name,
                'products': products,
                'totals': totals,
            })

        return report_data

    # ------------------------------------------------------------
    # EXCEL EXPORT (PROFESSIONAL)
    # ------------------------------------------------------------
    def action_export_xls(self):
        output = BytesIO()
        workbook = xlwt.Workbook()
        report_data = self.get_report_data()

        # Styles
        title_style = xlwt.easyxf('font: bold True, height 360; align: horiz center;')
        header_style = xlwt.easyxf(
            'font: bold True, colour white; pattern: pattern solid, fore_colour 0x2F;'
            'align: horiz center; borders: left thin, right thin, top thin, bottom thin;'
        )
        text_style = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin;')
        zebra_style = xlwt.easyxf('pattern: pattern solid, fore_colour 0x16; borders: left thin, right thin, top thin, bottom thin;')

        num_style = xlwt.easyxf(
            'align: horiz right; borders: left thin, right thin, top thin, bottom thin;',
            num_format_str='#,##0.00'
        )
        zebra_num = xlwt.easyxf(
            'pattern: pattern solid, fore_colour 0x16; align: horiz right;'
            'borders: left thin, right thin, top thin, bottom thin;',
            num_format_str='#,##0.00'
        )

        total_style = xlwt.easyxf(
            'font: bold True; pattern: pattern solid, fore_colour 0x2C;'
            'align: horiz right; borders: left thin, right thin, top thin, bottom thin;',
            num_format_str='#,##0.00'
        )
        total_text = xlwt.easyxf(
            'font: bold True; pattern: pattern solid, fore_colour 0x2C;'
            'borders: left thin, right thin, top thin, bottom thin;'
        )

        for location in report_data['lines']:
            sheet = workbook.add_sheet(location['location_name'][:31])

            widths = [8000, 4000] + [4200] * 12
            for i, w in enumerate(widths):
                sheet.col(i).width = w

            # Freeze
            sheet.set_panes_frozen(True)
            sheet.set_horz_split_pos(5)

            # Title
            sheet.write_merge(0, 0, 0, 13, "INVENTORY VALUATION REPORT", title_style)
            sheet.write_merge(1, 1, 0, 13, location['location_name'], text_style)
            sheet.write_merge(2, 2, 0, 13, f"Company: {report_data['company'].name}", text_style)
            sheet.write_merge(3, 3, 0, 13, f"Period: {report_data['start_date']} to {report_data['end_date']}", text_style)

            headers = [
                'Product', 'Costing',
                'Begin Qty', 'Begin Value',
                'In Qty', 'In Value',
                'Out Qty', 'Out Value',
                'Internal Qty', 'Internal Value',
                'Adjust Qty', 'Adjust Value',
                'End Qty', 'End Value'
            ]

            for col, h in enumerate(headers):
                sheet.write(4, col, h, header_style)

            row = 5
            zebra = False

            for prod in location['products']:
                style_txt = zebra_style if zebra else text_style
                style_num = zebra_num if zebra else num_style

                values = [
                    prod['name'], prod['costing_method'],
                    prod['beginning_qty'], prod['beginning_value'],
                    prod['received_qty'], prod['received_value'],
                    prod['sales_qty'], prod['sales_value'],
                    prod['internal_qty'], prod['internal_value'],
                    prod['adjustment_qty'], prod['adjustment_value'],
                    prod['ending_qty'], prod['ending_value'],
                ]

                for col, val in enumerate(values):
                    if col < 2:
                        sheet.write(row, col, val, style_txt)
                    else:
                        sheet.write(row, col, val, style_num)

                zebra = not zebra
                row += 1

            totals = location['totals']
            sheet.write_merge(row, row, 0, 1, "GRAND TOTAL", total_text)

            keys = [
                'beginning_qty','beginning_value','received_qty','received_value',
                'sales_qty','sales_value','internal_qty','internal_value',
                'adjustment_qty','adjustment_value','ending_qty','ending_value'
            ]

            col = 2
            for k in keys:
                sheet.write(row, col, totals[k], total_style)
                col += 1

        workbook.save(output)
        file_data = base64.b64encode(output.getvalue())
        output.close()

        self.write({
            'file_name': 'inventory_valuation_report.xls',
            'data': file_data
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=inventory.valuation.report&id={self.id}&field=data&download=true&filename=inventory_valuation_report.xls',
            'target': 'self',
        }
