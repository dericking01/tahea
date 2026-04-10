# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

{
    'name': 'Employee Multi Survey, Employee Survey',
    'version': '1.0',
    'sequence': 1,
    'category': 'Generic Modules/Human Resources',
    'description':
        """
        This Module add below functionality into odoo

        1.Employee Multi Survey\n
        
Employee multi survey in Odoo
Odoo employee survey management
Multi-survey functionality for employees in Odoo
Benefits of employee multi surveys in Odoo
Conducting surveys for employees in Odoo
Employee feedback and engagement with multi surveys in Odoo
Enhancing employee satisfaction through multi surveys in Odoo
Customizing multi surveys for employee feedback in Odoo
Streamlining employee survey processes in Odoo
Odoo multi-survey module for comprehensive employee feedback
Analyzing employee responses through multi surveys in Odoo
Employee performance evaluation with multi surveys in Odoo
Odoo multi-survey best practices for employee engagement
Tracking employee sentiments with multi surveys in Odoo
Enhancing HR decision-making with employee multi surveys in Odoo   

odoo app allow to add Employee Survey , employee surevey history to know answer, employee survey feddback, employee survey processes, employee mutltuple survey, employee survey list, employee survey question and answer     

    """,
    'summary': 'odoo app allow to add Employee Survey , employee surevey history to know answer, employee survey feddback, employee survey processes, employee mutltuple survey, employee survey list, employee survey question and answer',
    'depends': ['hr','survey'],
    'data': [
        'security/ir.model.access.csv',
        'data/email_send_survey.xml',
        'views/employee.xml'
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':10.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
