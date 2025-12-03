{
    'name': 'Monthly Payroll Report In Excel',
    'version': '1.0',
    'category': 'Payroll',
    'sequence': 60,
    'summary': 'Generates payroll reports in XLSX format for the selected month.',
    'description': """
This module provides an Excel (XLSX) report of employee payroll for a given month,
including salary components as per the payroll rules configured in the system.
""",
    'author': 'Stephen Ngailo, Powersoft Communications Ltd',
    'depends': [
        'base',
        'hr',
        'hr_payroll',  # Use Enterprise version
    ],
    'data': [
        # Security access (optional)
        # 'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/payroll_report_wiz.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
