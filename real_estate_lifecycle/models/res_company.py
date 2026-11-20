# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError

CHARGE_PRODUCT_FIELDS = {
    'rent': 're_product_rent_id',
    'service_charge': 're_product_service_charge_id',
    'parking': 're_product_parking_id',
    'marketing_levy': 're_product_marketing_id',
    'utility': 're_product_utility_id',
    'utility_fixed': 're_product_utility_id',
    'turnover_rent': 're_product_turnover_id',
    'other': 're_product_other_id',
    'concession': 're_product_rent_id',
    'service_charge_recon': 're_product_service_charge_id',
    'maintenance': 're_product_maintenance_id',
    'capex': 're_product_capex_id',
}

DEFAULT_PRODUCT_XMLIDS = {
    're_product_rent_id': 'real_estate_lifecycle.product_re_rent',
    're_product_service_charge_id': 'real_estate_lifecycle.product_re_service_charge',
    're_product_parking_id': 'real_estate_lifecycle.product_re_parking',
    're_product_marketing_id': 'real_estate_lifecycle.product_re_marketing_levy',
    're_product_utility_id': 'real_estate_lifecycle.product_re_utility',
    're_product_turnover_id': 'real_estate_lifecycle.product_re_turnover_rent',
    're_product_other_id': 'real_estate_lifecycle.product_re_other_charge',
    're_product_maintenance_id': 'real_estate_lifecycle.product_re_maintenance_service',
    're_product_capex_id': 'real_estate_lifecycle.product_re_capital_works',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Products used on invoices / purchase orders (income / expense accounts and
    # taxes come from the accountant's product configuration - nothing hardcoded)
    re_product_rent_id = fields.Many2one('product.product', 'Rent Product')
    re_product_service_charge_id = fields.Many2one('product.product', 'Service Charge Product')
    re_product_parking_id = fields.Many2one('product.product', 'Parking Product')
    re_product_marketing_id = fields.Many2one('product.product', 'Marketing Levy Product')
    re_product_utility_id = fields.Many2one('product.product', 'Utility Recharge Product')
    re_product_turnover_id = fields.Many2one('product.product', 'Turnover Rent Product')
    re_product_other_id = fields.Many2one('product.product', 'Other Charges Product')
    re_product_maintenance_id = fields.Many2one('product.product', 'Maintenance Service Product (OPEX)')
    re_product_capex_id = fields.Many2one('product.product', 'Capital Works Product (CAPEX)')

    re_rental_journal_id = fields.Many2one('account.journal', 'Rental Invoice Journal',
                                           domain="[('type', '=', 'sale')]")
    re_deposit_account_id = fields.Many2one(
        'account.account', 'Tenant Deposit Liability Account',
        help='Liability account credited when a security deposit is invoiced. Refundable deposits are '
             'never recognised as income.')
    re_deposit_deduction_account_id = fields.Many2one(
        'account.account', 'Deposit Deduction Income Account',
        help='Account credited for approved deductions retained from a deposit (e.g. damages).')
    re_auto_post_invoices = fields.Boolean('Auto-post Rental Invoices', default=False,
                                           help='If unchecked, generated rental invoices stay in draft for accountant review.')
    re_billing_grace_days = fields.Integer('Missing Invoice Grace (days)', default=3)
    re_lease_alert_days = fields.Char('Lease Expiry Alert Days', default='30,60,90,120',
                                      help='Comma separated list of days before expiry at which alerts are raised.')
    re_expiring_days = fields.Integer('Lease "Expiring" Window (days)', default=90)

    re_noi_include_other_income = fields.Boolean('Include "Other Income" accounts in NOI', default=False)
    re_noi_excluded_account_ids = fields.Many2many(
        'account.account', 'res_company_re_noi_excluded_rel', 'company_id', 'account_id',
        string='Accounts excluded from NOI',
        help='e.g. interest / financing costs, income tax, depreciation recorded on expense accounts.')

    re_block_unapproved_tenant_credit = fields.Boolean(
        'Block unapproved tenant credit notes', default=False,
        help='If set, posting a credit note for a lease requires adjustment approval. Otherwise it is posted and '
             'flagged by the revenue-assurance checks.')
    re_block_bill_over_approved = fields.Boolean('Block vendor bills above approved work-order budget', default=True)
    re_bill_tolerance_pct = fields.Float('Vendor Bill Tolerance (%)', default=5.0)
    re_require_po_for_contractor = fields.Boolean(
        'Require Purchase Order for contractor work', default=True,
        help='Direct vendor bills for contractor work orders (without PO) are flagged as control exceptions.')
    re_cluster_threshold = fields.Integer('Shared-issue Threshold (complaints)', default=2)
    re_cluster_window_days = fields.Integer('Shared-issue Window (days)', default=14)
    re_collection_case_days = fields.Integer('Open collection case after (days overdue)', default=30)
    re_collection_min_amount = fields.Monetary('Minimum overdue amount for collection case', currency_field='currency_id')
    re_wo_tolerance_pct = fields.Float('Work-order Overrun Tolerance (%)', default=10.0)

    def _re_set_default_products(self):
        for company in self:
            vals = {}
            for fname, xmlid in DEFAULT_PRODUCT_XMLIDS.items():
                if not company[fname]:
                    product = self.env.ref(xmlid, raise_if_not_found=False)
                    if product:
                        vals[fname] = product.id
            if vals:
                company.write(vals)

    def _re_get_product(self, charge_type):
        self.ensure_one()
        fname = CHARGE_PRODUCT_FIELDS.get(charge_type, 're_product_other_id')
        product = self[fname]
        if not product:
            xmlid = DEFAULT_PRODUCT_XMLIDS.get(fname)
            product = xmlid and self.env.ref(xmlid, raise_if_not_found=False)
        if not product:
            raise UserError(_('No product configured for "%(type)s" charges in company %(company)s. '
                              'Configure it in Real Estate > Configuration > Settings.',
                              type=charge_type, company=self.name))
        return product

    def _re_alert_days(self):
        self.ensure_one()
        days = []
        for part in (self.re_lease_alert_days or '').split(','):
            part = part.strip()
            if part.isdigit():
                days.append(int(part))
        return sorted(set(days), reverse=True) or [90]
