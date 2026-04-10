{
    'name': 'Monthly Payroll Report In Excel',
    'version': '1.0',
    'category': 'payroll',
    'sequence': 60,
    'summary': 'shows the payroll report in xlsx format',
    'description': "It shows payroll report in excel for given month",
    'author':'Stephen Ngailo, StiloTech Limited',
    'depends': ['base','hr', 'hr_payroll'],
    'data': [
      # 'security/security.xml',
      'security/ir.model.access.csv',
      'wizard/payroll_report_wiz.xml',

      ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
