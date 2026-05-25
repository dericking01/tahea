# -*- coding: utf-8 -*-
{
    'name': 'Equipment Management',
    'version': '1.0',
    'category': 'Operations',
    'summary': 'Simple Equipment Management System',
    'description': """
        Manage Equipment, Models, and Manufacturers.
        Simple structure with basic fields.
    """,
    'author': 'Mr Odoo',
    'depends': ['base',"mail","helpdesk","sale_management"],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/action_menu.xml',
        'views/equipment_tracking.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}