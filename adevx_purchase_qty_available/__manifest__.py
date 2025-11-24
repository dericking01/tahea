{
    'name': 'Purchase Qty Available',

    'summary': 'Qty Available In Purchase Order',
    'description': 'Qty Available In Purchase Order',

    'author': 'Adevx',
     "category": "Purchases",
    "license": "OPL-1",
    'website': 'https://adevx.com',

    'depends': ['purchase_stock'],
    'data': [
        # views
        'views/purchase_order.xml',
    ],

    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
