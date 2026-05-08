{
    'name': "Cashier Report",
    'version': '18.0.1.0.0',
    'category': 'Sales/Reports',
    'summary': "Record total sales per shop and payment method",
    'description': """
Cashier Report Management
=========================
This module allows you to:
- Record daily cashier reports per shop
- Track sales by wholesale and retail
- Summarize totals by payment method
- Record transactions with references
    """,
    'author': "Powersoft Solutions Ltd",
    'website': "https://www.powersoft.co.tz",
    'license': 'LGPL-3',
    'depends': ['base','hr', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/cashier_report_views.xml',
        'views/pivot_cashier_report.xml',
        'views/report_cashier_pdf.xml',
        'views/cashier_wizard_views.xml',
        # 'views/report_cashier_periodic.xml',
        'views/menuitems.xml',        
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
