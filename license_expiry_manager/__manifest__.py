{
    "name": "License & Subscription Expiry Manager",
    "version": "1.0",
    "category": "Administration",
    "summary": "Manage licenses, subscriptions and get expiry email reminders",
    "depends": ["mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/mail_template.xml",
        "data/cron.xml",
        "views/license_views.xml",
        "views/report_license.xml",
    ],
    "installable": True,
    "application": True,
}
