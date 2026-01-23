{
    'name': 'Restrict Product Creation',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Restrict product creation to specific users only',
    'description': """
Only users in special group can create products.
Others can only select existing products in Sales, Purchase, Inventory, etc.
""",
    'depends': ['base', 'product', 'sale', 'purchase', 'stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_field_restrictions.xml',
    ],
    'installable': True,
    'application': False,
}
