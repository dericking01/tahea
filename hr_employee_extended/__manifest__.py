{
    'name': 'HR Employee Extended',
    'version': '1.0',
    'summary': 'Adds TIN and NSSF fields to Employee',
    'description': """
        This module extends HR Employee to add:
        - Tax Identification Number (TIN)
        - National Social Security Fund (NSSF) Number
    """,
    'author': 'Derrick King',
    'website': 'https://www.pcl.co.tz',
    'category': 'Human Resources',
    'depends': ['hr','hr_contract'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}