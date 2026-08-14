{
    'name': 'Sales Company Approval',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'sequence': -14,
    'summary': 'Company-based approval workflow for Sales Orders',
    'depends': [
        'sale_management',
    ],
    'data': [
    'security/ir.model.access.csv',
    'views/res_company_views.xml',
    'views/sale_order_views.xml',
    'views/sale_order_report.xml',
],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}