{
    'name': 'Product Automatic Internal Reference',
    'version': '1.0',
    'summary': '',
    'sequence': 10,
    'author': 'The Fish Consulting',
    'website': 'https://thefishconsulting.be',
    'images': ['static/description/product_categories_arborescence.png'],
    'description': """

    """,
    'category': 'Inventory/Inventory',
    'depends': ['stock'],
    'data': [
        'views/product_category_views.xml',
        'views/product_product_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
    ],
    'price': 0.0,
    'currency': 'EUR',
    'support': 'contact@thefishconsulting.be',
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
