{
    "name": "Sale Order Line Qty On Hand",
    "version": "18.0.1.0.0",
    "summary": "Displays product quantity on hand on each sales order line",
    "description": """
Show Qty On Hand on Sales Order Line
====================================

This module adds a computed field to show the real-time stock
quantity on hand for the selected product on each sale order line.
    """,
    "author": "Powersoft Solutions Ltd",
    "website": "https://www.powersoft.co.tz",
    "category": "Sales",
    "depends": ["sale_management", "stock"],
    "data": [
        "views/views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
