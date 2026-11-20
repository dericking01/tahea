# -*- coding: utf-8 -*-
from odoo import Command, fields
from odoo.tests import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class ReCommon(AccountTestInvoicingCommon):
    """Shared fixture: one company configured for real estate, a property with a
    building, floor and five units, and one user per main role."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.env.user.groups_id |= cls.env.ref('real_estate_lifecycle.group_re_admin')
        cls.deposit_account = cls.env['account.account'].create({
            'name': 'Tenant Deposits Held', 'code': 'TDEP01', 'account_type': 'liability_current',
            'company_ids': [Command.set(cls.company.ids)]})
        cls.deduction_account = cls.env['account.account'].create({
            'name': 'Deposit Deductions Income', 'code': 'TDED01', 'account_type': 'income_other',
            'company_ids': [Command.set(cls.company.ids)]})
        cls.company.write({
            're_deposit_account_id': cls.deposit_account.id,
            're_deposit_deduction_account_id': cls.deduction_account.id,
            're_auto_post_invoices': True,
        })
        cls.company._re_set_default_products()
        # rental products get the test company income account (accountant configuration)
        income = cls.company_data['default_account_revenue']
        expense = cls.company_data['default_account_expense']
        for xmlid in ('product_re_rent', 'product_re_service_charge', 'product_re_parking', 'product_re_utility',
                      'product_re_turnover_rent', 'product_re_other_charge', 'product_re_marketing_levy'):
            cls.env.ref('real_estate_lifecycle.%s' % xmlid).property_account_income_id = income
        for xmlid in ('product_re_maintenance_service', 'product_re_capital_works'):
            cls.env.ref('real_estate_lifecycle.%s' % xmlid).property_account_expense_id = expense

        def user(login, groups):
            return new_test_user(cls.env, login=login, groups=','.join(groups), company_id=cls.company.id,
                                 company_ids=[(6, 0, cls.company.ids)])
        cls.pm = user('re_pm', ['real_estate_lifecycle.group_re_property_manager'])
        cls.approver = user('re_portfolio', ['real_estate_lifecycle.group_re_portfolio_manager'])
        cls.accountant = user('re_acc', ['real_estate_lifecycle.group_re_accountant'])
        cls.fin_manager = user('re_fm', ['real_estate_lifecycle.group_re_finance_manager'])
        cls.technician = user('re_tech', ['real_estate_lifecycle.group_re_technician'])
        cls.mm = user('re_mm', ['real_estate_lifecycle.group_re_maintenance_manager'])
        cls.investor = user('re_inv', ['real_estate_lifecycle.group_re_investor'])

        cls.ptype = cls.env.ref('real_estate_lifecycle.property_type_apartment')
        cls.lease_type = cls.env.ref('real_estate_lifecycle.lease_type_residential')
        cls.property = cls.env['re.property'].create({
            'name': 'Msasani Heights', 'code': 'MSH', 'property_type_id': cls.ptype.id,
            'company_id': cls.company.id, 'manager_id': cls.pm.id, 'region': 'Dar es Salaam',
            'district': 'Kinondoni', 'purchase_price': 1_000_000_000, 'state': 'active'})
        cls.building = cls.env['re.building'].create({'name': 'Block A', 'code': 'A', 'property_id': cls.property.id})
        cls.floor = cls.env['re.floor'].create({'name': 'Ground', 'level': 0, 'building_id': cls.building.id})
        cls.units = cls.env['re.unit'].create([{
            'name': 'A-%s' % i, 'property_id': cls.property.id, 'building_id': cls.building.id,
            'floor_id': cls.floor.id, 'unit_type': 'apartment', 'area': 50 + 10 * i,
            'market_rent': 2_000_000} for i in range(1, 6)])
        cls.tenant = cls.env['res.partner'].create({'name': 'Amani Traders Ltd', 'email': 'amani@example.com'})

    # ------------------------------------------------------------------
    @classmethod
    def _make_lease(cls, units=None, tenant=None, start='2026-01-01', end='2027-12-31', rent=2_000_000, **kw):
        vals = {
            'tenant_id': (tenant or cls.tenant).id, 'property_id': cls.property.id,
            'building_id': cls.building.id, 'unit_ids': [(6, 0, (units or cls.units[:1]).ids)],
            'lease_type_id': cls.lease_type.id, 'date_start': start, 'date_end': end,
            'rent_amount': rent, 'billing_frequency': 'monthly', 'deposit_amount': 0.0,
            'user_id': cls.pm.id,
        }
        vals.update(kw)
        return cls.env['re.lease'].create(vals)

    @classmethod
    def _activate(cls, lease):
        lease.with_user(cls.pm).action_submit()
        if lease.state == 'to_approve':
            lease.with_user(cls.approver).action_approve()
        lease.action_activate()
        return lease

    def _pay(self, move, amount, date=None):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids).create({
                'amount': amount, 'payment_date': date or move.invoice_date or fields.Date.today()})
        return wizard._create_payments()

    def _bill(self, lease, date_to):
        return self.env['re.billing.schedule']._cron_generate_rental_invoices(fields.Date.to_date(date_to), lease.ids)
