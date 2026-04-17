{
    'name': 'Sale Quotation Reference',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Add a Reference on quotations and propagate it to invoices',
    'description': """
Add a custom Reference field on quotations under the Customer field
and copy it automatically to invoices created from those quotations.
    """,
    'author': 'PrimeSoft Technologies',
    'depends': ['sale_management', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
