{
    'name': "Custom Invoice Statement Report",
    'summary': "Cash/Bank statement-style report for posted customer invoices "
               "grouped by payment status and journal type.",
    'description': """
Custom Invoice Report (Statement Reports)
==========================================

Adds a **Custom Invoice Report** entry under
``Accounting -> Reporting -> Statement Reports``.

The report covers **posted customer invoices** (``account.move``,
``move_type = 'out_invoice'``, ``state = 'posted'``) issued within a
user-selected date range and presents them:

* Grouped by native Odoo **payment status** (``payment_state``): Paid,
  Partially Paid, Not Paid, and Other (reversed / blocked / legacy).
* Grouped by **journal type** (``account.journal.type``) of the payment(s)
  that actually settled the invoice: Cash or Bank. Journals of any other
  type (sale, purchase, general, credit, ...) are not a valid settlement
  method and invoices settled that way (or not settled at all) fall in an
  "Other / Unclassified" bucket, kept out of the Cash/Bank breakdown table
  but still counted in the global summary.

Both a polished PDF (QWeb) and an Excel (XLSX) export are available from
the same wizard, sharing a single aggregation method so both formats are
always consistent with each other.
""",
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'author': "Custom Development",
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/report_paperformat.xml',
        'wizard/statement_invoice_report_wizard_views.xml',
        'report/statement_invoice_report_views.xml',
        'report/statement_invoice_pdf_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
