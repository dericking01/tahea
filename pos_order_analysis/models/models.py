from odoo import fields, models


class ReportPosOrder(models.Model):
    _inherit = 'report.pos.order'

    amount_untaxed = fields.Float(string='Untaxed Amount', readonly=True)
    amount_tax = fields.Float(string='Tax Amount', readonly=True)

    def _select(self):
        # report.pos.order is one row per order line (no GROUP BY) in 18.0,
        # so the measures are computed per line and summed by the pivot.
        return super()._select() + """,
            ROUND(l.price_subtotal / COALESCE(NULLIF(s.currency_rate, 0), 1.0), cu.decimal_places) AS amount_untaxed,
            ROUND((l.price_subtotal_incl - l.price_subtotal) / COALESCE(NULLIF(s.currency_rate, 0), 1.0), cu.decimal_places) AS amount_tax
        """
