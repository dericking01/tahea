# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class ReTenantAgeing(models.Model):
    """Tenant ageing based on open native receivable journal items.

    * Amounts are residuals in company currency.
    * Bucket = days between today and the due date (date_maturity).
    * Disputed invoices are shown separately from confirmed overdue debt.
    * Negative residuals are unallocated receipts / credits (advance payments,
      overpayments or credit notes not yet matched)."""
    _name = 're.tenant.ageing'
    _description = 'Tenant Ageing'
    _auto = False
    _order = 'days_overdue desc'

    move_line_id = fields.Many2one('account.move.line', readonly=True)
    move_id = fields.Many2one('account.move', 'Document', readonly=True)
    move_type = fields.Selection([('out_invoice', 'Invoice'), ('out_refund', 'Credit Note'), ('entry', 'Payment / Entry'),
                                  ('out_receipt', 'Receipt')], readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Tenant', readonly=True)
    lease_id = fields.Many2one('re.lease', readonly=True)
    property_id = fields.Many2one('re.property', readonly=True)
    building_id = fields.Many2one('re.building', readonly=True)
    portfolio_id = fields.Many2one('re.portfolio', readonly=True)
    manager_id = fields.Many2one('res.users', 'Property Manager', readonly=True)
    owner_id = fields.Many2one('res.partner', 'Property Owner', readonly=True)
    date = fields.Date(readonly=True)
    date_maturity = fields.Date('Due Date', readonly=True)
    days_overdue = fields.Integer(readonly=True, aggregator='max')
    is_disputed = fields.Boolean('Is Disputed', readonly=True)
    is_deposit = fields.Boolean('Deposit Demand', readonly=True)
    is_unallocated = fields.Boolean('Unallocated Credit', readonly=True)
    bucket = fields.Selection([('current', 'Current'), ('1_30', '1-30'), ('31_60', '31-60'), ('61_90', '61-90'),
                               ('90_plus', '90+'), ('credit', 'Unallocated credit')], readonly=True)
    amount_residual = fields.Monetary('Balance', readonly=True)
    amount_current = fields.Monetary('Current', readonly=True)
    amount_1_30 = fields.Monetary('1-30 days', readonly=True)
    amount_31_60 = fields.Monetary('31-60 days', readonly=True)
    amount_61_90 = fields.Monetary('61-90 days', readonly=True)
    amount_90_plus = fields.Monetary('90+ days', readonly=True)
    amount_disputed = fields.Monetary('Disputed', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
            WITH base AS (
                SELECT l.id, l.id AS move_line_id, l.move_id, m.move_type, l.company_id,
                       l.company_currency_id AS currency_id, p.commercial_partner_id AS partner_id,
                       m.re_lease_id AS lease_id,
                       COALESCE(m.re_property_id, l.re_property_id, ls.property_id) AS property_id,
                       COALESCE(m.re_building_id, l.re_building_id, ls.building_id) AS building_id,
                       l.date, COALESCE(l.date_maturity, l.date) AS date_maturity,
                       GREATEST(0, CURRENT_DATE - COALESCE(l.date_maturity, l.date)) AS days_overdue,
                       (m.re_dispute_state = 'open') AS is_disputed,
                       (m.re_deposit_id IS NOT NULL) AS is_deposit,
                       (l.amount_residual < 0) AS is_unallocated,
                       l.amount_residual
                  FROM account_move_line l
                  JOIN account_move m ON m.id = l.move_id
                  JOIN account_account a ON a.id = l.account_id
                  JOIN res_partner p ON p.id = l.partner_id
                  JOIN res_partner cp ON cp.id = p.commercial_partner_id
             LEFT JOIN re_lease ls ON ls.id = m.re_lease_id
                 WHERE a.account_type = 'asset_receivable'
                   AND l.parent_state = 'posted'
                   AND NOT l.reconciled
                   AND l.amount_residual != 0
                   AND (m.re_lease_id IS NOT NULL OR cp.re_is_tenant)
            )
            SELECT b.*, pr.portfolio_id, pr.manager_id, pr.legal_owner_id AS owner_id,
                   CASE WHEN b.is_unallocated THEN 'credit'
                        WHEN b.days_overdue = 0 THEN 'current'
                        WHEN b.days_overdue <= 30 THEN '1_30'
                        WHEN b.days_overdue <= 60 THEN '31_60'
                        WHEN b.days_overdue <= 90 THEN '61_90'
                        ELSE '90_plus' END AS bucket,
                   CASE WHEN NOT b.is_disputed AND (b.days_overdue = 0 OR b.is_unallocated)
                        THEN b.amount_residual ELSE 0 END AS amount_current,
                   CASE WHEN NOT b.is_disputed AND NOT b.is_unallocated AND b.days_overdue BETWEEN 1 AND 30
                        THEN b.amount_residual ELSE 0 END AS amount_1_30,
                   CASE WHEN NOT b.is_disputed AND NOT b.is_unallocated AND b.days_overdue BETWEEN 31 AND 60
                        THEN b.amount_residual ELSE 0 END AS amount_31_60,
                   CASE WHEN NOT b.is_disputed AND NOT b.is_unallocated AND b.days_overdue BETWEEN 61 AND 90
                        THEN b.amount_residual ELSE 0 END AS amount_61_90,
                   CASE WHEN NOT b.is_disputed AND NOT b.is_unallocated AND b.days_overdue > 90
                        THEN b.amount_residual ELSE 0 END AS amount_90_plus,
                   CASE WHEN b.is_disputed THEN b.amount_residual ELSE 0 END AS amount_disputed
              FROM base b
         LEFT JOIN re_property pr ON pr.id = b.property_id
            )
        """ % self._table)
