# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).


{
    'name': "Default Terms & Conditions (Purchase)",
    'version': '18.0.1.0',
    'category': 'Inventory/Purchase',
    'license': 'OPL-1',
    'author': "Kanak Infosystems LLP.",
    'website': "https://www.kanakinfosystems.com",
    'summary': '''This module is used to set Default Terms & Conditions on your Purchase Orders and PO report.''',
    'description': '''
        This module is used to set Default Terms & Conditions
        on your Purchase Orders and PO report.
        =================
    ''',
    'depends': ['base', 'purchase'],
    'images': ['static/description/banner.jpg'],
    'data': [
        'views/purchase_view.xml',
    ],
    'installable': True,
}
