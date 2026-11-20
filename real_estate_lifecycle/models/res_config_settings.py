# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    re_product_rent_id = fields.Many2one(related='company_id.re_product_rent_id', readonly=False)
    re_product_service_charge_id = fields.Many2one(related='company_id.re_product_service_charge_id', readonly=False)
    re_product_parking_id = fields.Many2one(related='company_id.re_product_parking_id', readonly=False)
    re_product_marketing_id = fields.Many2one(related='company_id.re_product_marketing_id', readonly=False)
    re_product_utility_id = fields.Many2one(related='company_id.re_product_utility_id', readonly=False)
    re_product_turnover_id = fields.Many2one(related='company_id.re_product_turnover_id', readonly=False)
    re_product_other_id = fields.Many2one(related='company_id.re_product_other_id', readonly=False)
    re_product_maintenance_id = fields.Many2one(related='company_id.re_product_maintenance_id', readonly=False)
    re_product_capex_id = fields.Many2one(related='company_id.re_product_capex_id', readonly=False)
    re_rental_journal_id = fields.Many2one(related='company_id.re_rental_journal_id', readonly=False)
    re_deposit_account_id = fields.Many2one(related='company_id.re_deposit_account_id', readonly=False)
    re_deposit_deduction_account_id = fields.Many2one(related='company_id.re_deposit_deduction_account_id', readonly=False)
    re_auto_post_invoices = fields.Boolean(related='company_id.re_auto_post_invoices', readonly=False)
    re_billing_grace_days = fields.Integer(related='company_id.re_billing_grace_days', readonly=False)
    re_lease_alert_days = fields.Char(related='company_id.re_lease_alert_days', readonly=False)
    re_expiring_days = fields.Integer(related='company_id.re_expiring_days', readonly=False)
    re_noi_include_other_income = fields.Boolean(related='company_id.re_noi_include_other_income', readonly=False)
    re_noi_excluded_account_ids = fields.Many2many(related='company_id.re_noi_excluded_account_ids', readonly=False)
    re_block_unapproved_tenant_credit = fields.Boolean(related='company_id.re_block_unapproved_tenant_credit', readonly=False)
    re_block_bill_over_approved = fields.Boolean(related='company_id.re_block_bill_over_approved', readonly=False)
    re_bill_tolerance_pct = fields.Float(related='company_id.re_bill_tolerance_pct', readonly=False)
    re_require_po_for_contractor = fields.Boolean(related='company_id.re_require_po_for_contractor', readonly=False)
    re_cluster_threshold = fields.Integer(related='company_id.re_cluster_threshold', readonly=False)
    re_cluster_window_days = fields.Integer(related='company_id.re_cluster_window_days', readonly=False)
    re_collection_case_days = fields.Integer(related='company_id.re_collection_case_days', readonly=False)
    re_collection_min_amount = fields.Monetary(related='company_id.re_collection_min_amount', readonly=False,
                                               currency_field='currency_id')
    re_wo_tolerance_pct = fields.Float(related='company_id.re_wo_tolerance_pct', readonly=False)
