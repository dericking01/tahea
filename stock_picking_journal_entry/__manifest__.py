{
    'name': 'Stock Picking Journal Entries',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'View journal entries from receipts and delivery orders',
    'description': """
        Stock Picking Journal Entries
        ==============================

        Adds a Journal Entries smart button to:
        - Receipts
        - Delivery Orders

        The button displays accounting journal entries
        related to the stock operation.
    """,
    'author': 'Primesoft Technologies',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'stock_account',
    ],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
}