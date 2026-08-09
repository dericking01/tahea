{
    'name': "OSCON Accounts",
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': "Show and filter the analytic account(s) directly on the invoices list view",
    'description': """
Adds an "Analytic" column to the Customer Invoices list view, showing the
analytic account(s) distributed on the invoice lines, and allows filtering
invoices by analytic account from the search panel.
""",
    'author': "OSCON",
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
