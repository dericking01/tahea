{
    'name': 'Zalongwa TRA EFD Integration',
    'version': '18.0.1.5.0',
    'summary': 'Tanzania TRA Electronic Fiscal Device (EFD) Integration via Zalongwa WebSHOP VEFD API',
    'description': """
        Full TRA EFD integration for Odoo 18:
        - Authenticate with Zalongwa WebSHOP API
        - Generate TRA receipts from Invoices
        - QR Code on invoice TRA receipt validation
        - View receipts and Z-Reports
    """,
    'author': 'Primesoft Technologies Limited',
    'website': 'https://www.primesoft.co.tz',
    'category': 'Accounting/Localizations',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/tra_efd_data.xml',
        'data/tra_efd_cron.xml',
        'views/tra_config_views.xml',
        'views/tra_receipt_views.xml',
        'views/tra_zreport_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/tra_dashboard_views.xml',
        'views/tra_menu.xml',
        'wizard/tra_receipt_confirm_views.xml',
        'report/invoice.xml',
        'report/tra_receipt_report.xml',
        'report/tra_receipt_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'zalongwa_tra_efd/static/src/js/tra_dashboard.js',
            'zalongwa_tra_efd/static/src/xml/tra_dashboard.xml',
            'zalongwa_tra_efd/static/src/scss/tra_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
