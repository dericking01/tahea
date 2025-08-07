# -*- coding: utf-8 -*-
{
    'name': "Contract Management (CallOff)",

    'summary': "Manage contracts with multiple call-off orders and automated expiry notifications",

    'description': """
This module allows users to manage contracts that include multiple call-off orders.
Each order has its own delivery timeline, status tracking (Pending, In Progress, Completed),
and expiration reminders. Designed for structured, deadline-driven contract execution.
    """,

    'author': "Powersoft Solutions Ltd",
    'website': "https://www.powersoft.co.tz",

    'category': 'Contracts',
    'version': '1.0',

    'depends': ['base', 'mail'],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        # 'data/contract_cron.xml',
    ],

    'demo': [],

    'installable': True,
    'application': True,
    'auto_install': False,
}
