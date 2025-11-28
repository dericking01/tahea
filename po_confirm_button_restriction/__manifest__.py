{
    'name': 'PO Confirm Order Button Visibility',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Modify Confirm Order button visibility based on RFQ status',
    'description': """
        This module makes the 'Confirm Order' button visible only when RFQ status is 'Sent'
        and hides it in all other statuses including 'Draft'.
    """,
    'author': 'Powesoft Communications Ltd',
    'website': 'https://pcl.co.tz',
    'depends': ['purchase'],
    'data': [
        'views/purchase_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}