{
    'name': 'Hide Payslip Number of Hours',
    'version': '18.0.1.0.0',
    'category': 'Payroll',
    'summary': 'Hides the Number of Hours column in employee payslips',
    'depends': ['hr_payroll'],
    'data': [
        'views/hr_payslip_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
