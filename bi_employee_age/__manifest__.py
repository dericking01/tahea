# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name" : "HR Employee Age",
    "version" : "16.0.0.1",
    "category" : "Employee",
    'license': 'OPL-1',
    'summary': "This odoo app helps to show employee age, On entering employee date of birth, employee age will automatically displayed.",
    "description": """
    
        This odoo app helps to show employee age, On entering employee date of birth, employee age will automatically displayed.
    
    """,
    "author": "BrowseInfo",
    "website" : "https://www.browseinfo.com",
    "price": 000,
    "currency": 'EUR',
    "depends" : ['hr'],
    "data": [
        'views/hr_inherit_views.xml',   
    ],
    "qweb" : [],
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://youtu.be/_tiPcOH7l70',
    "images":["static/description/Banner.gif"],
}
