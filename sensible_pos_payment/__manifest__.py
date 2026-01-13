# Powered by Sensible Consulting Services
# -*- coding: utf-8 -*-
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
{
    'name': 'POS Payment & Invoice',
    'version': '18.0.1.0',
    'summary': '''POS Payment & Invoice''',
    'description': '''The POS Payment & Invoice app for Odoo streamlines the payment and invoicing process directly 
        from your Point of Sale (POS) system. This app allows users to easily process customer payments and register 
        them against their invoices, ensuring seamless integration between your sales and accounting workflows.
    ''',
    'category': 'Sales/Point of Sale',
    'author': 'Sensible Consulting Services',
    'website': 'https://sensiblecs.com',
    'license': 'AGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sbl_account_payment_view.xml',
        'views/sbl_res_config_settings_views.xml',
        'wizard/sbl_account_payment_register_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'sensible_pos_payment/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
}
