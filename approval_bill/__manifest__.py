{
    'name': 'Approval to Vendor Bill',
    'version': '1.1',
    'summary': 'Create Vendor Bill from Approval Requests',
    'category': 'Accounting',
    'author': 'Primesoft Communications Ltd',
    'depends': ['approvals', 'account'],
    'data': [
        'views/views.xml',
        'views/report_templates.xml',
        'data/link_bill_action.xml',
    ],
    'installable': True,
    'application': False,
}
