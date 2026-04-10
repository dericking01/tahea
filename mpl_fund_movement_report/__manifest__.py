# -*- coding: utf-8 -*-
#
#    Meghsundar Private Limited(<https://www.meghsundar.com>).
#
{
    'name': 'Fund Movement Report',
    'version': '16.0.1',
    'summary': 'Fund Movement Report',
    'description': 'Fund Movement Report',
    'category': 'Extra Tools',
    'author': 'Meghsundar Private Limited',
    'website': 'https://www.meghsundar.com',
    'license': 'LGPL-3',
    'depends': ['bt_asset_management'],
    'data': [
        'security/ir.model.access.csv',
        'reports/fund_movement_report.xml',
        'reports/report.xml',
        'wizard/fund_movement_wizard_view.xml',
    ],
    'installable': True,
    'auto_install': False
}
