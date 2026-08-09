from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    oscon_analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        string='Analytic',
        compute='_compute_oscon_analytic_account_ids',
        search='_search_oscon_analytic_account_ids',
        help="Analytic accounts distributed on the invoice lines.",
    )

    @api.depends('invoice_line_ids.analytic_distribution')
    def _compute_oscon_analytic_account_ids(self):
        for move in self:
            move.oscon_analytic_account_ids = move.invoice_line_ids.mapped('distribution_analytic_account_ids')

    def _search_oscon_analytic_account_ids(self, operator, value):
        return [('invoice_line_ids.analytic_distribution', operator, value)]
