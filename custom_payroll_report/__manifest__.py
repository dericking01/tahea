{
    'name': 'Custom Payroll Report',
    'version': '1.0',
    'summary': 'Custom employee fields and payroll Excel report',
    'category': 'Human Resources',
    'author': 'Derrick Kamara',
    'website': 'https://www.pcl.co.tz',
    'depends': ['hr', 'hr_payroll', 'base', 'hr_work_entry_contract_enterprise'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'wizard/payroll_report_wizard.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}