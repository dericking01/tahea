# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2022. All rights reserved.

{
    "name": "Donation Analysis Report",
    "version": "13.0.0.0.1",
    "category": "Accounting & Finance",
    'license': 'Other proprietary',
    "summary": "Donation Analysis Report",
    'author': 'Technaureus Info Solutions Pvt. Ltd.',
    'website': 'http://www.technaureus.com/',
    "depends": ["donation_base", "project", "donation"],
    "data": [
        "views/donation_report_pdf.xml",
        "views/donation.xml",
        "report/report.xml",
        "report/invoice_external_layout.xml",
        "wizard/donation_report.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
