{
    'name': 'Sale & Purchase Order Enhancements',
    'version': '18.0.1.0.0',
    'summary': 'Qty On Hand column on SO/PO lines, and employee-based Salesperson on SO',
    'description': """
Sale & Purchase Order Enhancements
===================================

Adds a "Qty On Hand" column to the order lines table on the Sales Order
and Purchase Order forms, so users can see how much stock is available
for a product without leaving the order and navigating to the product's
inventory view.

- Sales Order lines: quantity on hand in the order's warehouse.
- Purchase Order lines: quantity on hand in the order's receiving warehouse.

Also replaces the Sales Order "Salesperson" field with an employee picker:

- Any employee can be selected, not just internal users in the Sales group.
- If the employee has no login yet, one is created automatically (using
  their work email) and granted Sales access, then set as Salesperson.
- A note is logged in the order's chatter whenever a new login is created
  this way.
""",
    'category': 'Sales/Sales',
    'author': 'Odoo Custom Development',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'purchase_stock', 'hr'],
    'data': [
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
