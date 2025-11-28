{
    'name': 'Purchase Sequential Approval (Role-Based)',
    'version': '1.0.0',
    'summary': 'Sequential 3-level PO approval: Operations -> Chief Controller -> Finance',
    'category': 'Purchases',
    'author': 'Mr. Odoo / Powersoft Solutions',
    'website': 'https://example.com',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'mail',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/purchase_order_report_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
