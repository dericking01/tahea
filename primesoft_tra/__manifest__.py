{
    'name': 'Primesoft TRA EFD Integration',
    'version': '18.0.2.0.0',
    'summary': 'Tanzania TRA fiscal receipts for Invoices and Point of Sale via the Zalongwa WebSHOP VEFD API',
    'description': """
        TRA EFD integration for Odoo 18:
        - Authenticate with the Zalongwa WebSHOP API
        - Generate TRA receipts from Invoices, from Point of Sale orders, or both
        - TRA QR code on the invoice and on the POS receipt
        - Receipts, Z-Reports and a dashboard
    """,
    'author': 'Primesoft Technologies Limited',
    'website': 'https://www.primesoft.co.tz',
    'category': 'Accounting/Localizations',
    'depends': ['account', 'point_of_sale'],
    'external_dependencies': {'python': ['qrcode', 'requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/tra_efd_data.xml',
        'data/tra_efd_cron.xml',
        'views/tra_config_views.xml',
        'views/tra_receipt_views.xml',
        'views/tra_zreport_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/pos_views.xml',
        'views/tra_dashboard_views.xml',
        'views/tra_menu.xml',
        'wizard/tra_receipt_confirm_views.xml',
        'report/invoice.xml',
        'report/tra_receipt_report.xml',
        'report/tra_receipt_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'primesoft_tra/static/src/js/tra_dashboard.js',
            'primesoft_tra/static/src/xml/tra_dashboard.xml',
            'primesoft_tra/static/src/scss/tra_dashboard.scss',
        ],
        'point_of_sale._assets_pos': [
            'primesoft_tra/static/src/js/PosOrder.js',
            'primesoft_tra/static/src/js/payment.js',
            'primesoft_tra/static/src/xml/payment_screen_toggle.xml',
            'primesoft_tra/static/src/js/receipt_screen.js',
            'primesoft_tra/static/src/xml/OrderReceipt.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
