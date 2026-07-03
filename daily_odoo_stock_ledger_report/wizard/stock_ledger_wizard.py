from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class StockLedgerWizard(models.TransientModel):
    """
    Wizard for selecting a date range to generate the stock ledger report.
    Defaults to the previous calendar month.
    """
    _name = 'stock.ledger.wizard'
    _description = 'Stock Ledger Wizard'

    date_from = fields.Date(string="From", required=True)
    date_to = fields.Date(string="To", required=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Ensure date_from is not after date_to."""
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError("The 'From' date cannot be after the 'To' date.")

    @api.model
    def default_get(self, fields_list):
        """Set default dates to the start and end of the previous calendar month."""
        res = super().default_get(fields_list)
        today = fields.Date.today()
        last_day_last_month = today.replace(day=1) - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)

        res.update({
            'date_from': first_day_last_month,
            'date_to': last_day_last_month,
        })
        return res

    def action_generate(self):
        """
        Store the selected date range in context and open the product list view.
        Only storable products are shown.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Ledger',
            'res_model': 'product.product',
            'view_mode': 'list',
            'target': 'current',
            'domain': [('is_storable', '=', True)],
            'context': {
                'date_from': str(self.date_from),
                'date_to': str(self.date_to),
            },
        }