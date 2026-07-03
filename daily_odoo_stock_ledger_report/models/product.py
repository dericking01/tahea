from odoo import models

# Global CSS Constants for Dashboard layout
CSS_CLASS_DASHBOARD_ROW = "g-col-6 g-col-md-6 grid gap-1 gap-md-4"
CSS_CLASS_LABEL = "g-col-12 g-col-sm-4 g-col-lg-3 d-flex align-items-center justify-content-center text-center justify-content-md-end text-md-end mt-4 mt-sm-0 text-break"
CSS_CLASS_VALUE = "g-col-12 g-col-sm-8 g-col-lg-9 d-flex align-items-center justify-content-center py-2 px-3 bg-100"
CSS_CLASS_BREAKDOWN_LABEL = "g-col-12 g-col-sm-4 g-col-lg-3 d-flex align-items-start justify-content-center text-center justify-content-md-end text-md-end mt-4 mt-sm-0 text-break pt-2"
CSS_CLASS_BREAKDOWN_VALUE = "g-col-12 g-col-sm-8 g-col-lg-9 d-flex align-items-start justify-content-center py-2 px-4 bg-100"

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_stock_ledger(self):
        self.ensure_one()
        
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')
        
        self._clear_previous_report_data()
        
        location_balances = {}
        opening_balance = self._calculate_opening_balance(date_from, location_balances)
        
        dashboard_html = self._get_dashboard_html(date_from, date_to, opening_balance, location_balances)
        
        self._process_stock_moves_and_create_ledger_lines(date_from, date_to, opening_balance, location_balances)
        
        return self._get_ledger_action(dashboard_html)

    def _clear_previous_report_data(self):
        self.env['stock.ledger.line'].search([('create_uid', '=', self.env.uid)]).unlink()

    def _update_location_balance(self, location, quantity, location_balances):
        if location.id not in location_balances:
            location_balances[location.id] = {
                'warehouse_name': location.warehouse_id.name or 'Undefined',
                'location_name': location.display_name, 
                'stock_quantity': 0.0
            }
        location_balances[location.id]['stock_quantity'] += quantity

    def _format_location_balances_to_html(self, location_balances, is_dashboard=False):
        warehouses = {}
        for location_id, data in location_balances.items():
            if round(data['stock_quantity'], 2) == 0:
                continue
            
            warehouse_name = data['warehouse_name']
            if warehouse_name not in warehouses:
                warehouses[warehouse_name] = []
            warehouses[warehouse_name].append(data)
        
        if not warehouses:
            return ""

        html_parts = []
        for warehouse_name, locations in warehouses.items():
            total_quantity = sum(loc['stock_quantity'] for loc in locations)
            
            container_style = 'margin-bottom: 8px; width: 100%; font-size: 0.9em;' if is_dashboard else 'margin-bottom: 8px; width: 160px; overflow-x: auto;'
            html_parts.append(f'<div style="{container_style}">')
            html_parts.append('<table style="width: 100%;">')
            
            html_parts.append(
                '<tr>'
                f'<td colspan="2" style="border-bottom: 1px solid #ddd; padding-bottom: 2px;"><span class="text-primary">{warehouse_name}</span></td>'
                f'<td style="text-align: right; border-bottom: 1px solid #ddd; padding-bottom: 2px;"><span class="text-primary">{total_quantity:.2f}</span></td>'
                '</tr>'
            )
            
            for loc in locations:
                html_parts.append(
                    '<tr style="font-size: 0.85em;">'
                    '<td style="width: 15px; vertical-align: top; color: #666; padding-top: 2px;">&#8226;</td>'
                    f'<td style="color: #444; font-style: italic; padding-top: 2px;">{loc["location_name"]}</td>'
                    f'<td style="text-align: right; padding-left: 15px; padding-top: 2px;">{loc["stock_quantity"]:.2f}</td>'
                    '</tr>'
                )
            html_parts.append('</table></div>')
        
        return "".join(html_parts)

    def _calculate_opening_balance(self, date_from, location_balances):
        opening_balance = 0
        moves = self.env['stock.move.line'].search([
            ('product_id', '=', self.id),
            ('date', '<', date_from),
            ('state', '=', 'done'),
            ('company_id', '=', self.env.company.id)
        ])

        for move in moves:
            if move.location_dest_id.usage == 'internal':
                opening_balance += move.quantity
                self._update_location_balance(move.location_dest_id, move.quantity, location_balances)
            if move.location_id.usage == 'internal':
                opening_balance -= move.quantity
                self._update_location_balance(move.location_id, -move.quantity, location_balances)
                
        return opening_balance

    def _get_dashboard_html(self, date_from, date_to, opening_balance, location_balances):
        breakdown_html = self._format_location_balances_to_html(location_balances, is_dashboard=True)
        
        return f"""
        <div class="o_purchase_dashboard container-fluid py-4 border-bottom bg-view">
            <div class="row justify-content-between gap-3 gap-lg-0">
                <div class="col-12 col-lg-12 col-xl-12 flex-shrink-0">
                    <div class="d-flex flex-column justify-content-between gap-2 h-100">
                        <div class="grid gap-2 h-100">
                            <div class="{CSS_CLASS_DASHBOARD_ROW}">
                                <div class="{CSS_CLASS_LABEL}">
                                    Product
                                </div>
                                <div class="{CSS_CLASS_VALUE}">
                                    <span class="fs-5 text-primary fw-bold text-truncate">{self.display_name}</span>
                                </div>
                            </div>
                            <div class="{CSS_CLASS_DASHBOARD_ROW}">
                                <div class="{CSS_CLASS_LABEL}">
                                    Period
                                </div>
                                <div class="{CSS_CLASS_VALUE}">
                                    <span>{date_from} <i class="fa fa-arrow-right mx-2 text-muted"></i> {date_to}</span>
                                </div>
                            </div>
                        </div>

                        <div class="grid gap-2 h-100">
                            <div class="{CSS_CLASS_DASHBOARD_ROW}">
                                <div class="{CSS_CLASS_LABEL}">
                                    Opening Balance
                                </div>
                                <div class="{CSS_CLASS_VALUE}">
                                    <span class="fs-4 text-primary fw-bold">{opening_balance:.2f}</span>
                                </div>
                            </div>
                            <div class="{CSS_CLASS_DASHBOARD_ROW}">
                                <div class="{CSS_CLASS_BREAKDOWN_LABEL}">
                                    Breakdown
                                </div>
                                <div class="{CSS_CLASS_BREAKDOWN_VALUE}" style="max-height: 120px; overflow-y: auto; overflow-x: hidden;">
                                    {breakdown_html}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    def _process_stock_moves_and_create_ledger_lines(self, date_from, date_to, running_balance, location_balances):
        moves = self.env['stock.move.line'].search([
            ('product_id', '=', self.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'done'),
            ('company_id', '=', self.env.company.id)
        ], order='date asc, id asc')

        for move in moves:
            incoming_quantity = 0
            outgoing_quantity = 0
            transaction_type = False
            
            source_is_internal = move.location_id.usage == 'internal'
            destination_is_internal = move.location_dest_id.usage == 'internal'

            if source_is_internal and destination_is_internal:
                incoming_quantity = move.quantity
                outgoing_quantity = move.quantity
                transaction_type = 'internal'
                self._update_location_balance(move.location_dest_id, move.quantity, location_balances)
                self._update_location_balance(move.location_id, -move.quantity, location_balances)
            elif destination_is_internal:
                incoming_quantity = move.quantity
                running_balance += incoming_quantity
                transaction_type = 'in'
                self._update_location_balance(move.location_dest_id, move.quantity, location_balances)
            elif source_is_internal:
                outgoing_quantity = move.quantity
                running_balance -= outgoing_quantity
                transaction_type = 'out'
                self._update_location_balance(move.location_id, -move.quantity, location_balances)
            else:
                continue

            self.env['stock.ledger.line'].create({
                'product_id': self.id,
                'date': move.date,
                'from_location': move.location_id.id,
                'to_location': move.location_dest_id.id,
                'in_qty': incoming_quantity,
                'out_qty': outgoing_quantity,
                'transaction_type': transaction_type,
                'balance': running_balance,
                'location_balances_html': self._format_location_balances_to_html(location_balances),
            })

    def _get_ledger_action(self, dashboard_html):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Ledger',
            'res_model': 'stock.ledger.line',
            'view_mode': 'list',
            'target': 'current',
            'domain': [('create_uid', '=', self.env.uid)],
            'context': {
                'stock_ledger_dashboard_html': dashboard_html
            }
        }