# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    'name': "Purchase Order Multi Product Selection",
    'version': "18.0.0.1",
    'summary': "This module allows you to select Multiple product in purchase order at a time on single click.",
    'category': 'Purchases',
    'description': """
        This module allows you to select Multiple product in purchase order on single click.
         Purchase order add multi product
         product add
         multiple product add in purchase order quickly
         easy add product in purchase order on single click
         create purchase order from product
    """,
    'author': "Sitaram",
    'website': "sitaramsolutions.in",
    'depends': ['base', 'purchase', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase.xml',
        'views/product.xml'
    ],
    'demo': [],
    "license": "OPL-1",
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
