{
    'name': 'POS Hide Invoice Button',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Hides the Invoice button on the POS payment screen',
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_invoice_hidden/static/src/overrides/components/payment_screen/payment_screen.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}
