import base64
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import LazyTranslate

from ..models.account_move import PAYMENT_STATE_BUCKETS

_lt = LazyTranslate(__name__)

BUCKET_LABELS = {
    'paid': _lt("Paid"),
    'partial': _lt("Partially Paid"),
    'not_paid': _lt("Unpaid"),
    'other': _lt("Other"),
}
CASH_BANK_LABELS = {
    'cash': _lt("Cash"),
    'bank': _lt("Bank"),
    'other': _lt("Other / Unclassified"),
}
DATE_BASIS_LABELS = {
    'invoice_date': _lt("Invoice Date"),
    'payment_date': _lt("Payment Date"),
}
# Filtering by Payment Date turns this from "which invoices were issued in
# this window" into "which invoices were paid in this window" -- a
# collections/sales view rather than an invoicing one -- so the report
# title changes to match what the reader is actually looking at.
REPORT_TITLES = {
    'invoice_date': _lt("Custom Invoice Report"),
    'payment_date': _lt("Custom Sales Report"),
}
FILENAME_PREFIXES = {
    'invoice_date': "Custom_Invoice_Report",
    'payment_date': "Custom_Sales_Report",
}


def _empty_bucket_totals():
    return {'count': 0, 'amount': 0.0}


class StatementInvoiceReportWizard(models.TransientModel):
    _name = 'statement.invoice.report.wizard'
    _description = "Custom Invoice Report Wizard"

    date_basis = fields.Selection(
        selection=[
            ('invoice_date', "Invoice Date"),
            ('payment_date', "Payment Date"),
        ],
        string="Filter By",
        required=True,
        default='invoice_date',
        help="Invoice Date: include invoices issued within the selected "
             "range, regardless of when (or whether) they were later paid. "
             "This is what most people mean by \"invoices for January\".\n\n"
             "Payment Date: include invoices that received at least one "
             "payment within the selected range, regardless of when they "
             "were issued (e.g. a December invoice settled in January "
             "would show up under January). Amounts shown are still each "
             "invoice's full value, not just the portion paid in this "
             "window, and invoices with no payment at all can never appear "
             "in this mode -- use Invoice Date if you also need to see "
             "unpaid invoices.",
    )
    date_from = fields.Date(string="Date From", required=True,
                             default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string="Date To", required=True,
                           default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                  default=lambda self: self.env.company)

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("Date From cannot be later than Date To."))

    # ------------------------------------------------------------------
    # Data aggregation
    #
    # Both the PDF and the XLSX export call this single method so the two
    # output formats can never disagree with each other, and so the
    # (potentially large) invoice set is only queried once per report run.
    # ------------------------------------------------------------------
    def _get_domain(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]
        if self.date_basis == 'payment_date':
            # account.payment.reconciled_invoice_ids is the native reverse
            # link from a payment to the (customer) invoices it settles
            # (see account.payment._compute_reconciled_invoice_ids); going
            # through it rather than a dotted domain on account.move's own
            # computed reconciled_payment_ids keeps this a plain, reliable
            # two-query lookup. 'draft'/'canceled'/'rejected' payments never
            # represent real cash movement, so they're excluded.
            payments = self.env['account.payment'].sudo().search([
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', 'in', ('in_process', 'paid')),
            ])
            domain.append(('id', 'in', payments.reconciled_invoice_ids.ids))
        else:
            domain += [
                ('invoice_date', '>=', self.date_from),
                ('invoice_date', '<=', self.date_to),
            ]
        return domain

    def _get_report_data(self):
        """Build the full aggregated dataset used by both the PDF and the
        XLSX report.

        Multi-currency note: invoices can be issued in different
        currencies. Summing ``amount_total``/``amount_residual`` (expressed
        in each invoice's own currency) across invoices would silently mix
        currencies and produce a meaningless number, so all summary and
        breakdown totals are computed from ``amount_total_signed`` /
        ``amount_residual_signed``, which Odoo's accounting engine already
        stores in the *company* currency for every journal item. Because
        this report is scoped to customer invoices only (never credit
        notes), these signed amounts are simply the invoice total/residual
        converted to company currency, so they can be summed safely at the
        database level via ``_read_group``. The company currency is shown
        next to every aggregated figure. Per-invoice rows in the detailed
        section instead show the amount in the invoice's own currency, so
        no conversion is silently applied at that level.
        """
        self.ensure_one()
        # sudo(): this report is also reachable from Sales -> Reporting so
        # sales managers can pull it without being separately granted
        # Accounting access, but read access to account.move itself is
        # restricted to account.group_account_manager/readonly/invoice
        # (see account's ir.model.access.csv) and a Sales Manager isn't a
        # member of any of those by default. The security boundary for who
        # can see this read-only, aggregated invoice data is therefore
        # enforced at the wizard level instead (ir.model.access.csv grants
        # this TransientModel to account.group_account_invoice/readonly
        # *and* sales_team.group_sale_manager, and both menu items require
        # one of those groups to even be reachable) rather than relying on
        # the caller's own account.move rights.
        AccountMove = self.env['account.move'].sudo()
        domain = self._get_domain()
        company_currency = self.company_id.currency_id

        # ---- DB-level aggregation: one query for the whole matrix -------
        # Grouping by statement_settlement_journal_id (in addition to type
        # and payment status) gives the per-journal drill-down -- e.g. how
        # much of "Bank" is specifically "Selcom" vs. "CRDB" -- without a
        # second query: the type-level rows are just this same data summed
        # back up across journals.
        groups = AccountMove._read_group(
            domain,
            groupby=['statement_cash_bank_type', 'statement_settlement_journal_id', 'payment_state'],
            aggregates=['__count', 'amount_total_signed:sum', 'amount_residual_signed:sum'],
        )

        # breakdown[cash_bank_type][bucket] = {'count': int, 'amount': float}
        breakdown = {
            key: {bucket: _empty_bucket_totals() for bucket in ('paid', 'partial', 'not_paid', 'other')}
            for key in ('cash', 'bank', 'other')
        }
        # journal_breakdown[cash_bank_type][journal][bucket] = {'count', 'amount'}
        journal_breakdown = {'cash': {}, 'bank': {}}
        residual_by_type = {'cash': 0.0, 'bank': 0.0, 'other': 0.0}

        for cash_bank_type, journal, payment_state, count, total_signed, residual_signed in groups:
            bucket = PAYMENT_STATE_BUCKETS.get(payment_state, 'other')
            entry = breakdown[cash_bank_type][bucket]
            entry['count'] += count
            entry['amount'] += total_signed
            residual_by_type[cash_bank_type] += residual_signed

            if journal:  # empty recordset for the 'other' bucket (no settlement journal)
                journal_buckets = journal_breakdown[cash_bank_type].setdefault(
                    journal, {b: _empty_bucket_totals() for b in ('paid', 'partial', 'not_paid', 'other')}
                )
                j_entry = journal_buckets[bucket]
                j_entry['count'] += count
                j_entry['amount'] += total_signed

        def _row(cash_bank_type):
            buckets = breakdown[cash_bank_type]
            count = sum(b['count'] for b in buckets.values())
            amount = sum(b['amount'] for b in buckets.values())
            return {
                'key': cash_bank_type,
                'label': self.env._(CASH_BANK_LABELS[cash_bank_type]),
                'count': count,
                'amount': amount,
                'paid_amount': buckets['paid']['amount'],
                'partial_amount': buckets['partial']['amount'],
                'not_paid_amount': buckets['not_paid']['amount'],
                'other_amount': buckets['other']['amount'],
            }

        def _journal_row(journal, buckets):
            count = sum(b['count'] for b in buckets.values())
            amount = sum(b['amount'] for b in buckets.values())
            return {
                'label': journal.name,
                'count': count,
                'amount': amount,
                'paid_amount': buckets['paid']['amount'],
                'partial_amount': buckets['partial']['amount'],
                'not_paid_amount': buckets['not_paid']['amount'],
            }

        cash_row = _row('cash')
        bank_row = _row('bank')
        other_row = _row('other')

        # Per-journal sub-rows for each type, biggest contributor first.
        journal_rows = {
            cash_bank_type: sorted(
                (_journal_row(journal, buckets) for journal, buckets in journal_breakdown[cash_bank_type].items()),
                key=lambda r: r['amount'], reverse=True,
            )
            for cash_bank_type in ('cash', 'bank')
        }
        total_row = {
            'label': _("Total"),
            'count': cash_row['count'] + bank_row['count'] + other_row['count'],
            'amount': cash_row['amount'] + bank_row['amount'] + other_row['amount'],
            'paid_amount': cash_row['paid_amount'] + bank_row['paid_amount'] + other_row['paid_amount'],
            'partial_amount': cash_row['partial_amount'] + bank_row['partial_amount'] + other_row['partial_amount'],
            'not_paid_amount': cash_row['not_paid_amount'] + bank_row['not_paid_amount'] + other_row['not_paid_amount'],
            'other_amount': cash_row['other_amount'] + bank_row['other_amount'] + other_row['other_amount'],
        }

        # ---- Global summary (payment-status buckets, cash/bank collapsed)
        summary_buckets = {bucket: _empty_bucket_totals() for bucket in ('paid', 'partial', 'not_paid', 'other')}
        for cash_bank_type in ('cash', 'bank', 'other'):
            for bucket, values in breakdown[cash_bank_type].items():
                summary_buckets[bucket]['count'] += values['count']
                summary_buckets[bucket]['amount'] += values['amount']

        total_amount = total_row['amount']
        total_residual = sum(residual_by_type.values())
        summary = {
            'invoice_count': total_row['count'],
            'total_amount': total_amount,
            'paid_amount': total_amount - total_residual,
            'outstanding_amount': total_residual,
            'buckets': {
                bucket: {
                    'label': self.env._(BUCKET_LABELS[bucket]),
                    'count': values['count'],
                    'amount': values['amount'],
                } for bucket, values in summary_buckets.items()
            },
        }

        # ---- Invoice-level detail ----------------------------------------
        invoices = AccountMove.search(domain, order='invoice_date asc, name asc')
        invoice_lines = []
        if invoices:
            invoices.fetch([
                'name', 'invoice_date', 'partner_id', 'journal_id',
                'statement_cash_bank_type', 'statement_settlement_journal_id',
                'amount_total', 'amount_residual',
                'payment_state', 'currency_id',
            ])
            for move in invoices:
                bucket = PAYMENT_STATE_BUCKETS.get(move.payment_state, 'other')
                invoice_lines.append({
                    'name': move.name,
                    'invoice_date': move.invoice_date,
                    'partner': move.partner_id.name or '',
                    'journal': move.journal_id.name or '',
                    'cash_bank_type': self.env._(CASH_BANK_LABELS[move.statement_cash_bank_type]),
                    'settlement_journal': move.statement_settlement_journal_id.name or '',
                    'amount_total': move.amount_total,
                    'amount_paid': move.amount_total - move.amount_residual,
                    'amount_due': move.amount_residual,
                    'payment_status': self.env._(BUCKET_LABELS[bucket]),
                    'currency': move.currency_id.name,
                    'currency_record': move.currency_id,
                })

        return {
            'company': self.company_id,
            'company_currency': company_currency,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'date_basis': self.date_basis,
            'date_basis_label': self.env._(DATE_BASIS_LABELS[self.date_basis]),
            'report_title': self.env._(REPORT_TITLES[self.date_basis]),
            # Kept naive (UTC): the QWeb 'datetime' widget localizes it to the
            # user's timezone itself and errors out on an already-localized
            # value. `_build_xlsx` localizes it explicitly for the Excel export.
            'generated_on': fields.Datetime.now(),
            'summary': summary,
            'breakdown_rows': [cash_row, bank_row],
            'journal_rows': journal_rows,
            'breakdown_total': total_row,
            'unclassified': other_row,
            'invoices': invoice_lines,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_generate_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'custom_invoice_statement_report.action_report_statement_invoice'
        ).report_action(self)

    def action_change_report_layout(self):
        """Open Odoo's native "Configure Document Layout" wizard on demand.

        ``report_action()`` only shows this wizard automatically the first
        time a company generates any PDF report (while
        ``company.external_report_layout_id`` is unset); afterwards it is
        remembered company-wide and every report, including this one, skips
        straight to rendering. This button reopens the same native wizard
        so users can change the branding/layout whenever they want, instead
        of duplicating Odoo's layout picker. ``config=False`` skips the
        automatic prompt (we are opening it explicitly here), and wiring
        the plain report action into the configurator's context makes it
        immediately (re)generate this PDF, with the new layout, once saved.
        """
        self.ensure_one()
        report = self.env.ref('custom_invoice_statement_report.action_report_statement_invoice')
        report_action = report.report_action(self, config=False)
        return self.env['ir.actions.report']._action_configure_external_report_layout(report_action)

    def action_generate_xlsx(self):
        self.ensure_one()
        try:
            import xlsxwriter  # noqa: F401
        except ImportError:
            raise UserError(_("The 'xlsxwriter' Python library is required to generate Excel reports."))

        data = self._get_report_data()
        xlsx_data = self._build_xlsx(data)

        attachment = self.env['ir.attachment'].create({
            'name': self._xlsx_filename(),
            'datas': base64.b64encode(xlsx_data),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true&filename={self._xlsx_filename()}",
            'target': 'self',
        }

    def _xlsx_filename(self):
        self.ensure_one()
        prefix = FILENAME_PREFIXES[self.date_basis]
        return f"{prefix}_{self.date_from}_{self.date_to}.xlsx"

    def _build_xlsx(self, data):
        """Build the Excel workbook. Kept as a plain method (not a
        report.xxx AbstractModel) since Odoo's core report engine only
        supports qweb-html/qweb-pdf/qweb-text natively; xlsxwriter is used
        directly, matching the pattern already used elsewhere in this
        codebase for Excel exports.
        """
        import xlsxwriter

        fp = BytesIO()
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True})

        fmt_title = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#1F4E78'})
        fmt_subtitle = workbook.add_format({'italic': True, 'font_size': 10, 'font_color': '#666666'})
        fmt_section = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_color': 'white',
            'bg_color': '#1F4E78', 'valign': 'vcenter', 'indent': 1,
        })
        fmt_kpi_label = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        fmt_kpi_value = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        fmt_kpi_int = workbook.add_format({'border': 1, 'num_format': '#,##0'})
        fmt_header = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#2E75B6',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        })
        fmt_cell = workbook.add_format({'border': 1})
        fmt_cell_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        fmt_cell_int = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'center'})
        fmt_total_label = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        fmt_total_num = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'num_format': '#,##0.00'})
        fmt_total_int = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'num_format': '#,##0', 'align': 'center'})
        fmt_date = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})
        # Payment-type subtotal (Cash / Bank) vs. its per-journal sub-rows
        fmt_type_label = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'border': 1})
        fmt_type_num = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'border': 1, 'num_format': '#,##0.00'})
        fmt_type_int = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'border': 1, 'num_format': '#,##0', 'align': 'center'})
        fmt_journal_label = workbook.add_format({'border': 1, 'indent': 2, 'font_color': '#404040'})
        fmt_journal_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'font_color': '#404040'})
        fmt_journal_int = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'center', 'font_color': '#404040'})

        currency_code = data['company_currency'].name

        # ================= Summary sheet =================
        ws = workbook.add_worksheet('Summary')
        ws.hide_gridlines(2)
        ws.set_column('A:A', 32)
        ws.set_column('B:B', 22)

        row = 0
        ws.merge_range(row, 0, row, 3, data['report_title'], fmt_title)
        row += 1
        ws.merge_range(row, 0, row, 3, data['company'].name, fmt_subtitle)
        row += 1
        generated_on_local = fields.Datetime.context_timestamp(self, data['generated_on'])
        ws.merge_range(row, 0, row, 3,
                        f"Period (by {data['date_basis_label']}): {data['date_from']} to {data['date_to']}  |  "
                        f"Generated: {generated_on_local.strftime('%Y-%m-%d %H:%M')}",
                        fmt_subtitle)
        row += 1
        if data['date_basis'] == 'payment_date':
            ws.merge_range(row, 0, row, 3,
                            "Filtered by Payment Date: only invoices with at least one payment in this "
                            "window are included (unpaid invoices cannot appear). Amounts shown are each "
                            "invoice's full value, not just the portion paid within this window.",
                            fmt_subtitle)
            row += 1
        row += 1

        ws.merge_range(row, 0, row, 1, "Summary", fmt_section)
        row += 1
        summary = data['summary']
        kpi_rows = [
            ("Total Posted Invoices", summary['invoice_count'], fmt_kpi_int),
            (f"Total Invoice Amount ({currency_code})", summary['total_amount'], fmt_kpi_value),
            (f"Total Paid Amount ({currency_code})", summary['paid_amount'], fmt_kpi_value),
            (f"Total Outstanding Amount ({currency_code})", summary['outstanding_amount'], fmt_kpi_value),
        ]
        for label, value, fmt in kpi_rows:
            ws.write(row, 0, label, fmt_kpi_label)
            ws.write(row, 1, value, fmt)
            row += 1
        row += 1

        ws.merge_range(row, 0, row, 3, "By Payment Status", fmt_section)
        row += 1
        ws.write_row(row, 0, ["Status", "Invoice Count", f"Amount ({currency_code})"], fmt_header)
        row += 1
        for bucket in ('paid', 'partial', 'not_paid', 'other'):
            b = summary['buckets'][bucket]
            if bucket == 'other' and not b['count']:
                continue
            ws.write(row, 0, b['label'], fmt_cell)
            ws.write(row, 1, b['count'], fmt_cell_int)
            ws.write(row, 2, b['amount'], fmt_cell_num)
            row += 1
        row += 1

        ws.merge_range(row, 0, row, 5, "Payment Type Breakdown (Cash / Bank)", fmt_section)
        row += 1
        headers = ["Payment Type", "Invoice Count", f"Total Invoice Amount ({currency_code})",
                   "Paid", "Partially Paid", "Unpaid"]
        ws.write_row(row, 0, headers, fmt_header)
        header_row = row
        row += 1
        for r in data['breakdown_rows']:
            ws.write(row, 0, r['label'], fmt_type_label)
            ws.write(row, 1, r['count'], fmt_type_int)
            ws.write(row, 2, r['amount'], fmt_type_num)
            ws.write(row, 3, r['paid_amount'], fmt_type_num)
            ws.write(row, 4, r['partial_amount'], fmt_type_num)
            ws.write(row, 5, r['not_paid_amount'], fmt_type_num)
            row += 1
            # Only worth a drill-down once a type has more than one
            # contributing journal; with a single one, the sub-row would
            # just repeat the subtotal above it.
            journal_rows_for_type = data['journal_rows'][r['key']]
            if len(journal_rows_for_type) > 1:
                for jr in journal_rows_for_type:
                    ws.write(row, 0, jr['label'], fmt_journal_label)
                    ws.write(row, 1, jr['count'], fmt_journal_int)
                    ws.write(row, 2, jr['amount'], fmt_journal_num)
                    ws.write(row, 3, jr['paid_amount'], fmt_journal_num)
                    ws.write(row, 4, jr['partial_amount'], fmt_journal_num)
                    ws.write(row, 5, jr['not_paid_amount'], fmt_journal_num)
                    row += 1
        t = data['breakdown_total']
        ws.write(row, 0, t['label'], fmt_total_label)
        ws.write(row, 1, t['count'], fmt_total_int)
        ws.write(row, 2, t['amount'], fmt_total_num)
        ws.write(row, 3, t['paid_amount'], fmt_total_num)
        ws.write(row, 4, t['partial_amount'], fmt_total_num)
        ws.write(row, 5, t['not_paid_amount'], fmt_total_num)
        row += 2
        if data['unclassified']['count']:
            ws.merge_range(row, 0, row, 5,
                            f"Note: {data['unclassified']['count']} invoice(s) totalling "
                            f"{data['unclassified']['amount']:,.2f} {currency_code} are not "
                            "settled via a Cash or Bank journal (unpaid, or settled through "
                            "another journal type) and are excluded from the Cash/Bank "
                            "breakdown above.", fmt_subtitle)
        ws.freeze_panes(header_row + 1, 0)

        # ================= Detail sheet =================
        ws2 = workbook.add_worksheet('Invoice Detail')
        ws2.hide_gridlines(2)
        col_widths = [16, 12, 28, 16, 14, 16, 14, 14, 14, 14, 10]
        for i, w in enumerate(col_widths):
            ws2.set_column(i, i, w)

        headers2 = ["Invoice Number", "Invoice Date", "Customer", "Journal",
                    "Journal Type", "Settlement Journal", "Invoice Amount", "Amount Paid",
                    "Amount Due", "Payment Status", "Currency"]
        ws2.write_row(0, 0, headers2, fmt_header)
        r = 1
        for line in data['invoices']:
            ws2.write(r, 0, line['name'], fmt_cell)
            ws2.write_datetime(r, 1, line['invoice_date'], fmt_date) if line['invoice_date'] else ws2.write(r, 1, '', fmt_cell)
            ws2.write(r, 2, line['partner'], fmt_cell)
            ws2.write(r, 3, line['journal'], fmt_cell)
            ws2.write(r, 4, line['cash_bank_type'], fmt_cell)
            ws2.write(r, 5, line['settlement_journal'], fmt_cell)
            ws2.write(r, 6, line['amount_total'], fmt_cell_num)
            ws2.write(r, 7, line['amount_paid'], fmt_cell_num)
            ws2.write(r, 8, line['amount_due'], fmt_cell_num)
            ws2.write(r, 9, line['payment_status'], fmt_cell)
            ws2.write(r, 10, line['currency'], fmt_cell)
            r += 1

        if data['invoices']:
            ws2.autofilter(0, 0, r - 1, len(headers2) - 1)
        ws2.freeze_panes(1, 0)

        workbook.close()
        fp.seek(0)
        content = fp.getvalue()
        fp.close()
        return content
