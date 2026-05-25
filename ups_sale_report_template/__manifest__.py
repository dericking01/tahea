# -*- coding: utf-8 -*-

{
	"name" : "UPS Sale Report Templates",
    "summary" : "Premium Sale Report Templates | Custom Colors, Watermarks & Branding | Fully Dynamic designs for Quotations & Sale Orders",
    "description" : """
        Transform your Odoo Sale Orders and Quotations with professional, high-end report designs. 
        This module provides 10 unique, fully customizable templates that allow you to modify colors, 
        add watermarks, and change paper formats with a single click. 
        
        Key Features:
        - Stunning Report Layouts
        - Dynamic Color Picker for Brand Alignment
        - Customizable Watermarks & Backgrounds
        - Multi-Company & Multi-Currency Support
        - One-Click Activation & Easy Setup
        - Responsive Design for Digital & Physical Prints
    """,
	"version" : "1.0",
	"depends" : [
		"base","sale","sale_management","ups_base_report_template"
	],

	"data" : [
		"security/ir.model.access.csv",
        "views/setting_sale_view.xml",
        "views/inherit_company_view.xml",
        "views/external_custom_layout.xml",
        "report/sale_report_template_1.xml",
        "report/sale_report_template_2.xml",
        "report/sale_report_template_3.xml",
        "report/sale_report_template_4.xml",
        "report/sale_report_template_5.xml",
        "report/sale_report_template_6.xml",
        "report/sale_report_template_7.xml",
        "report/sale_report_template_8.xml",
        "report/sale_report_template_9.xml",
        "report/sale_report_template_10.xml",
        "report/sale_report_inherit.xml",
        "report/sale_reports.xml",
	],

	'assets': {
        'web.report_assets_common': [
            'ups_sale_report_template/static/src/scss/external_layout.scss',
            'ups_sale_report_template/static/src/scss/sale_template_1.scss',
            'ups_sale_report_template/static/src/scss/sale_template_2.scss',
            'ups_sale_report_template/static/src/scss/sale_template_3.scss',
            'ups_sale_report_template/static/src/scss/sale_template_4.scss',
            'ups_sale_report_template/static/src/scss/sale_template_5.scss',
            'ups_sale_report_template/static/src/scss/sale_template_6.scss',
            'ups_sale_report_template/static/src/scss/sale_template_7.scss',
            'ups_sale_report_template/static/src/scss/sale_template_8.scss',
            'ups_sale_report_template/static/src/scss/sale_template_9.scss',
            'ups_sale_report_template/static/src/scss/sale_template_10.scss',
        ],
    },
    
    'author': 'Odoo S.A.',
	"installable" : True,
	"application": True,
	'license': 'LGPL-3',
}