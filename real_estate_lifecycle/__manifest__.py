# -*- coding: utf-8 -*-
{
    'name': 'Real Estate Lifecycle & Performance Management',
    'version': '18.0.1.0.0',
    'category': 'Real Estate',
    'sequence': 5,
    'summary': 'Property register, leasing, rental billing, revenue assurance, '
               'service charges, maintenance, vendors, investment appraisal and portfolio intelligence',
    'description': """
Real Estate Lifecycle & Performance Management (RE-LPM)
=======================================================
An integrated real estate operating environment for Odoo 18 Enterprise:

* Property, building, floor, unit and land/plot register with ownership history
* Leasing pipeline (CRM), lease contracts, approvals, amendments, escalations, renewals
* Idempotent rental billing through native Odoo customer invoices
* Security deposits held as liabilities, refunds through credit notes
* Service-charge budgets, allocation and year-end reconciliation
* Utility meters, readings and tenant recharges
* Collections, promises-to-pay, disputes and tenant ageing
* Revenue leakage and financial control exception engine
* Equipment register (extends Maintenance), work orders, preventive plans, replacement analysis
* Contractor register, RFQ/PO integration through native Purchase, performance metrics
* Property P&L / NOI through analytic accounting, executive dashboard
* Investment appraisal (NPV, IRR, payback, ROI, yields, break-even occupancy)
* Tenant and contractor portal
""",
    'author': 'RE-LPM',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'portal',
        'account',
        'analytic',
        'account_asset',
        'purchase',
        'maintenance',
        'crm',
    ],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/re_security.xml',
        'security/ir.model.access.csv',
        'security/re_rules.xml',
        'data/re_sequence_data.xml',
        'data/re_config_data.xml',
        'data/re_product_data.xml',
        'data/re_control_data.xml',
        'data/re_mail_template_data.xml',
        'data/re_cron_data.xml',
        'wizards/re_wizard_views.xml',
        'wizards/re_report_wizard_views.xml',
        'views/re_config_views.xml',
        'views/re_property_views.xml',
        'views/re_building_views.xml',
        'views/re_unit_views.xml',
        'views/re_lease_views.xml',
        'views/re_billing_views.xml',
        'views/re_deposit_views.xml',
        'views/re_service_charge_views.xml',
        'views/re_utility_views.xml',
        'views/re_collection_views.xml',
        'views/re_exception_views.xml',
        'views/re_ticket_views.xml',
        'views/re_work_order_views.xml',
        'views/re_maintenance_views.xml',
        'views/re_vendor_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/purchase_order_views.xml',
        'views/crm_lead_views.xml',
        'views/re_ageing_views.xml',
        'views/re_investment_views.xml',
        'views/re_approval_views.xml',
        'views/res_config_settings_views.xml',
        'views/re_dashboard_views.xml',
        'views/re_menus.xml',
        'reports/re_report_actions.xml',
        'reports/re_report_templates.xml',
        'views/re_portal_templates.xml',
    ],
    'demo': [
        'demo/re_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'real_estate_lifecycle/static/src/dashboard/*.js',
            'real_estate_lifecycle/static/src/dashboard/*.xml',
            'real_estate_lifecycle/static/src/dashboard/*.scss',
        ],
    },
    'post_init_hook': '_re_post_init_hook',
    'installable': True,
    'application': True,
}
