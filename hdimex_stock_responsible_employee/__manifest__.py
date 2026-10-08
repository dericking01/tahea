# -*- coding: utf-8 -*-
{
    'name': 'HDIMEX Transfer Responsible Employee',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Pick any employee as Responsible on transfers / delivery orders",
    'description': """
Replaces the 'Responsible' field in the Additional Info tab of transfers
(delivery orders, receipts, internal transfers) with an employee selector,
so all employees can be chosen, not only users with Inventory access.
When the selected employee has a linked user, the standard user
responsible is kept in sync so filters and activities keep working.
    """,
    'author': 'HDIMEX',
    'depends': ['stock', 'hr'],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
