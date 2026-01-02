# -*- coding: utf-8 -*-

{
    'name': 'POS Kitchen Receipt',
    'version': '1.01',
    'category': 'Point of Sale',
    'sequence': 6,
    'author': 'Webveer',
    'summary': 'This module allows you to print kitchen receipt without thermal printer.',
    'description': "This module allows you to print kitchen receipt without thermal printer",
    'depends': ['pos_restaurant'],
    'data': [
        'views/views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_kitchen_receipt/static/src/**/*',
        ],
    },
    'images': [
        'static/description/receipt.jpg',
    ],
    'installable': True,
    'website': '',
    'auto_install': False,
    'price': 40,
    'currency': 'EUR',
}
