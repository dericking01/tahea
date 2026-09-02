{
    'name': 'Approval to Vendor Bill',
    'version': '1.0',
    'summary': 'Create Vendor Bill from Approval Requests',
    'category': 'Accounting',
    'author': 'Powersoft Solutions Ltd',
    'depends': ['approvals', 'account'],
    'data': [
        'views/views.xml',
        'views/report_templates.xml',
    ],
    'installable': True,
    'application': False,
}
