{
    'name': 'Stock Ledger Report',
    'version': '18.0.1.0.1',
    'category': 'Inventory',
    'summary': 'Stock Ledger Report with Opening Balance and Running Balance for Inventory',
    'author': 'Ahex Technologies',
    'website': 'https://www.ahex.co',
    'sequence': 10,
    'description': """
        Stock Ledger Report provides a complete, line-by-line history of stock movements for any product with opening balance, incoming, outgoing, and running balance calculations.
    """,
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_view.xml',
        'wizard/stock_ledger_wizard_view.xml',
        'wizard/stock_ledger_line_view.xml',
    ],
    'images': ['static/description/banner.gif'],
    'price' : '19',
    'currency' : 'USD',
    "live_test_url": "https://youtu.be/UB50XN4eA7E",
    'license': 'OPL-1',
    'assets': {
        'web.assets_backend': [
            'daily_odoo_stock_ledger_report/static/src/views/stock_ledger_dashboard.xml',
            'daily_odoo_stock_ledger_report/static/src/views/stock_ledger_dashboard.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}