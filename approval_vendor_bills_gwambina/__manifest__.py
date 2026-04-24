{
    'name': 'Vendor Payment Approval',
    'version': '1.0',
    'summary': 'Select vendor bills in Approval Request with total amount',
    'category': 'Accounting',
    'author': 'Powersoft Solutions Ltd',
    'depends': ['approvals', 'account'],
    'data': [
        "security/ir.model.access.csv",
        'views/approval_request_views.xml',
    ],
    'installable': True,
    'application': False,
}
