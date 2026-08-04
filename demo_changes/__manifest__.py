# -*- coding: utf-8 -*-
{
    'name': 'Demo Changes',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Adds a Waste-Products tab to Manufacturing Orders',
    'description': """
        Adds a "Waste-Products" tab to the Manufacturing Order form,
        working the same way as the existing "By-Products" tab.
    """,
    'author': 'Demo',
    'depends': ['mrp'],
    'data': [
        'views/mrp_production_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
