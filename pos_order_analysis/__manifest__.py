# -*- coding: utf-8 -*-
{
    "name": "POS Order Analysis Extra Measures",

    'summary': """
        Untaxed/tax measures on POS Orders Analysis and a Sales / POS Excel export""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Point of Sale",
    'version': '18.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['sale_management', 'point_of_sale', 'account'],
    'external_dependencies': {'python': ['xlsxwriter']},

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/action.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3',
}
