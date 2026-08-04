{
    'name': 'Qty On Hand in Sales & Purchase Orders',
    'version': '18.0.1.0.0',
    'summary': 'Show product quantity on hand directly on Sales Order and Purchase Order lines',
    'description': """
Quantity On Hand on Sale & Purchase Order Lines
================================================

Adds a "Qty On Hand" column to the order lines table on the Sales Order
and Purchase Order forms, so users can see how much stock is available
for a product without leaving the order and navigating to the product's
inventory view.

- Sales Order lines: quantity on hand in the order's warehouse.
- Purchase Order lines: quantity on hand in the order's receiving warehouse.
""",
    'category': 'Sales/Sales',
    'author': 'Odoo Custom Development',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'purchase_stock'],
    'data': [
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
