# -*- coding: utf-8 -*-

###############################################################################
#                                                                             #
#    Aboutknowledge (Hong Kong) Limited.                                     #
#                                                                             #
#    Copyright (C) 2022-TODAY Aboutknowledge (Hong Kong) Limited             #
#    (<https://www.aboutknowledge.com/>)                                     #
#    Author: Aboutknowledge (Hong Kong) Limited                              #
#    (<https://www.aboutknowledge.com/>)                                     #
#                                                                             #
###############################################################################
{
    'name': 'Purchase Payment Status',
    'version': '18.0.1.0.0',
    'author': 'Aboutknowledge (Hong Kong) Limited',
    'company': 'Aboutknowledge (Hong Kong) Limited',
    'maintainer': 'Aboutknowledge (Hong Kong) Limited',
    'website': 'https://www.aboutknowledge.com/',
    'category': 'Purchases',
    'summary': 'Track vendor bill payments from Purchase Orders in real time',
    'description': """
This module enables automatic tracking of vendor bill payments directly from the Purchase Order form in Odoo 17.

Features:
---------
- Real-time vendor bill payment status (Not Paid, Partially Paid, Fully Paid)
- Adds visual indicators for payment tracking
- Links vendor bills to the respective Purchase Order
- No additional configuration needed
- Compatible with Community and Enterprise editions """,


'depends': ['base', 'purchase'],
    'data': [
        'security/abk_purchase_payment_status_group.xml',
        'views/abk_purchase_order_views.xml',
    ],
    'images': ['static/description/Banner.png'],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': True,
    'price': 4.99,
    'currency': 'USD',
}
