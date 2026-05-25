# -*- coding: utf-8 -*-

{
	"name" : "Invoice Report Templates",
	"version" : "1.0",
	"summary" : "Professional and customizable invoice report templates with 10 unique designs for Odoo.",
	"description" : """
	Invoice Report Templates provides a collection of beautifully designed and fully customizable invoice report layouts for Odoo.
	This module enhances standard invoice printing by adding multiple professional templates, custom external layouts, and configurable report settings.

	Features
		- 10 ready-to-use invoice report templates
		- Custom external invoice layouts
		- Invoice report configuration settings
		- Professional PDF invoice designs
		- Dedicated SCSS styling for each template
		- Seamless integration with Odoo Accounting
		- Support for branded and business-specific invoice formats
		- Easy template switching and customization
		- Modular QWeb report structure for easy extension
	Benefits
		- Improve invoice presentation and branding
		- Choose different layouts based on business needs
		- Enhance customer-facing accounting documents
		- Reduce customization effort with ready-made templates
	""",
	"depends" : [
		"base","account","ups_base_report_template"
	],

	"data" : [
        "views/setting_invoice_view.xml",
        "views/external_invoice_custom_layout.xml",
        "report/invoice_report_template_1.xml",
        "report/invoice_report_template_2.xml",
        "report/invoice_report_template_3.xml",
        "report/invoice_report_template_4.xml",
        "report/invoice_report_template_5.xml",
        "report/invoice_report_template_6.xml",
        "report/invoice_report_template_7.xml",
        "report/invoice_report_template_8.xml",
        "report/invoice_report_template_9.xml",
        "report/invoice_report_template_10.xml",
        "report/invoice_report_inherit.xml",
        "report/invoice_reports.xml",
	],
    
	"assets": {
			'web.report_assets_common': [
                'ups_invoice_report_template/static/src/scss/external_invoice_layout.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_1.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_2.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_3.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_4.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_5.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_6.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_7.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_8.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_9.scss',
				'ups_invoice_report_template/static/src/scss/invoice_template_10.scss',
			],
		},
        
    'author': 'Upstackers Technologies',
	'images': ['static/description/banner.png'],
	"installable" : True,
	"application": True,
	"license": 'LGPL-3',
}