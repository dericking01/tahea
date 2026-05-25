# -*- coding: utf-8 -*-

from odoo import models, fields
import io
import base64
import xlsxwriter
from datetime import datetime


class SalesVisitCancelWizard(models.TransientModel):
    _name = "sales.visit.cancel.wizard"
    _description = "Cancel Sales Visit"

    visit_id = fields.Many2one("sales.visit", required=True)
    reason = fields.Text(string="Cancellation Reason", required=True)

    def action_confirm(self):
        self.visit_id.write({
            "visit_status": "cancelled",
            "cancel_reason": self.reason,
        })
        self.visit_id.message_post(
            body=f"Visit Cancelled. Reason:<br/>{self.reason}"
        )


class SalesVisitPostponeWizard(models.TransientModel):
    _name = "sales.visit.postpone.wizard"
    _description = "Postpone Sales Visit"

    visit_id = fields.Many2one("sales.visit", required=True)
    reason = fields.Text(string="Postpone Reason", required=True)

    def action_confirm(self):
        self.visit_id.write({
            "visit_status": "postponed",
            "postpone_reason": self.reason,
        })
        self.visit_id.message_post(
            body=f"Visit Postponed. Reason:<br/>{self.reason}"
        )
    

class SalesVisitReportWizard(models.TransientModel):
    _name = "sales.visit.report.wizard"
    _description = "Sales Visit Report Wizard"

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)

    visit_status = fields.Selection(
        [
            ("planned", "Planned"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("postponed", "Postponed"),
        ],
        string="Visit Status",
    )

    file_data = fields.Binary("File")
    file_name = fields.Char("Filename")

    # ==========================================
    # GENERATE EXCEL
    # ==========================================

    def action_export_excel(self):

        import io
        import base64
        import xlsxwriter

        # Domain
        domain = [
            ("visit_date", ">=", self.start_date),
            ("visit_date", "<=", self.end_date),
        ]

        if self.visit_status:
            domain.append(("visit_status", "=", self.visit_status))

        visits = self.env["sales.visit"].search(domain)

        # Create file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Sales Visit Report")

        # ===============================
        # FORMATS
        # ===============================

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center'
        })

        subtitle_format = workbook.add_format({
            'italic': True,
            'align': 'center'
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0B3D91',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })

        date_format = workbook.add_format({
            'border': 1,
            'num_format': 'yyyy-mm-dd'
        })

        # ===============================
        # TITLE SECTION
        # ===============================

        sheet.merge_range('A1:M1', 'SALES VISIT REPORT', title_format)

        report_period = f"Period: {self.start_date} To {self.end_date}"
        sheet.merge_range('A2:M2', report_period, subtitle_format)

        sheet.set_row(0, 25)

        # ===============================
        # HEADERS START FROM ROW 4
        # ===============================

        headers = [
            "Reference", "Sales Rep", "Region", "Facility",
            "Facility Type", "Objective", "Plan Date",
            "Visit Date", "Status", "Person Met",
            "Phone", "Email", "Notes"
        ]

        for col, header in enumerate(headers):
            sheet.write(3, col, header, header_format)

        # Freeze panes
        sheet.freeze_panes(4, 0)

        # Enable filter
        sheet.autofilter(3, 0, 3 + len(visits), len(headers) - 1)

        # ===============================
        # DATA
        # ===============================

        row = 4

        for visit in visits:

            sheet.write(row, 0, visit.name or "", cell_format)
            sheet.write(row, 1, visit.sales_rep_id.name or "", cell_format)
            sheet.write(row, 2, visit.region or "", cell_format)
            sheet.write(row, 3, visit.facility_id.name or "", cell_format)
            sheet.write(row, 4, visit.facility_type or "", cell_format)
            sheet.write(row, 5, visit.objective or "", cell_format)

            sheet.write(row, 6, visit.plan_date or "", date_format)
            sheet.write(row, 7, visit.visit_date or "", date_format)

            sheet.write(row, 8, visit.visit_status or "", cell_format)
            sheet.write(row, 9, visit.person_met or "", cell_format)
            sheet.write(row, 10, visit.phone or "", cell_format)
            sheet.write(row, 11, visit.email or "", cell_format)
            sheet.write(row, 12, visit.notes or "", cell_format)

            row += 1

        # ===============================
        # AUTO COLUMN WIDTH
        # ===============================

        for col in range(len(headers)):
            sheet.set_column(col, col, 18)

        workbook.close()
        output.seek(0)

        file_content = base64.b64encode(output.read())
        filename = f"Sales_Visit_Report_{self.start_date}_to_{self.end_date}.xlsx"

        self.write({
            "file_data": file_content,
            "file_name": filename,
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/?model={self._name}&id={self.id}&field=file_data&download=true&filename={filename}",
            "target": "self",
        }