{
    'name': 'Inventory Categories Custom',
    'version': '18.0.1.0.0',
    'sequence': -15,
    'category': 'Inventory/Inventory',
    'summary': 'Restrict Product Categories by Company in Odoo 18',
    'description': """
        This module adds a company field to product categories, restricts them 
        using multi-company record rules, and filters them on the product form.
    """,
    'author': 'PrimeSoft Technologies Properties',
    'depends': ['product', 'stock'],
    'data': [
        'security/category_security.xml',
        'views/product_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}