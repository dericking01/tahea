{
    "name": "Field Sales Visit",
    "version": "1.0",
    "summary": "Field Sales Visit Tracker with CRM & Helpdesk Integration",
    "author": "Mr. Odoo",
    "depends": [
        "base",
        "mail",        # for chatter & activities
        "crm",         # for lead integration
        "helpdesk",    # optional but we include for now
        "calendar",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sales_visit_views.xml",
        "views/sales_visit_views_wizard.xml",
    ],
    "installable": True,
    "application": True,
}