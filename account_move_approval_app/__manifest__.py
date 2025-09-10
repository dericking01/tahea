# -*- coding: utf-8 -*-

{
    'name': 'Account Move Approval App',
    'author': 'Edge Technologies',
    'version': '16.0.1.0.0',
    'license': 'LGPL-3',
    'images':['static/description/main_screenshot.png'],
    'summary': 'Account Move Approval App',
    'description': """
        Account Move Approval App
    """,
    'depends': ['account'],
    'data': [
        'security/groups.xml',
        'views/account_move_view.xml',
        'views/account_move_views.xml',
        'views/account_voucher_view.xml',
        'views/account_payment_view.xml', 
        'report/report_account_voucher.xml'
    ],
    'installable': True,
    'auto_install': False,
    'currency': "EUR",
    'category': 'Accounting',
    'application': True,
    'sequence': 15,
}
