# -*- coding: utf-8 -*-
{
    'name': "Vendor Bill From GRN Picking",
    'summary': "Link Goods Receipt Notes (GRN) Picking with Vendor Bills",
    'description': """
This module allows seamless linking between Goods Receipt Notes (GRN) Picking and Vendor Bills.
        
        Features:
        - Inventory personnel create GRN Picking (Goods Receipt Notes)
        - Only authorized accountants can create Vendor Bills from GRN Picking
        - Automatic linking and bi-directional references
        - Chatter messages with clickable links between GRN and Bills
        - Track billing status of received goods
        - Role-based access control
""",
    'author': "Asksol",
    'website': "https://www.asksol.pk",
    'category': 'Inventory/Accounting',
    'version': '18.0.1.0',
    'license': "LGPL-3",

    'depends': ['base', 'stock', 'account'],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
    ],
    
    # 'price': 12.82,
    # 'currency': 'USD',

    'images': ['static/description/banner.png'],
        
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
