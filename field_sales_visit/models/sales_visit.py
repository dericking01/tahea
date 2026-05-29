# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta


class SalesVisit(models.Model):
    _name = "sales.visit"
    _description = "Daily Sales Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # =====================================================
    # BASIC INFORMATION
    # =====================================================

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )

    sales_rep_id = fields.Many2one(
        "res.users",
        string="Sales Rep",
        default=lambda self: self.env.user,
        tracking=True,
    )

    region = fields.Char(string="Region", tracking=True)

    facility_id = fields.Many2one(
        "res.partner",
        string="Facility",
        tracking=True,
    )

    facility_type = fields.Selection(
        [
            ("hospital", "Hospital"),
            ("clinic", "Clinic"),
            ("imaging_center", "Imaging Center"),
            ("laboratory", "Laboratory"),
            ("research", "Research Institution"),
            ("university", "University"),
            ("regulatory", "Regulatory Bodies"),
            ("other", "Other"),
        ],
        string="Facility Type",
        tracking=True,
    )

    objective = fields.Selection(
        [
            ("intro", "Introduction/Relationship Building"),
            ("product", "Product Presentation"),
            ("training", "Training/Application Support"),
            ("demo", "Demonstration"),
            ("service", "Service/Technical Support Visit"),
            ("follow_up", "Follow-up on Previous Discussion"),
            ("quotation", "Quotation Submission"),
            ("tender", "Tender Discussion"),
            ("negotiation", "Negotiation / Pricing Discussion"),
            ("contract", "Contract Signing / Agreement"),
            ("delivery", "Delivery / Installation Support"),
            ("after_sale", "After-Sales Support"),
            ("closing", "Closing the Deal"),
            ("customer_care", "Courtesy Visit / Customer Care"),
        ],
        string="Objective of Visit",
        tracking=True,
    )

    plan_date = fields.Date(string="Plan Date", tracking=True)
    visit_date = fields.Date(string="Visit Date", tracking=True)

    visit_status = fields.Selection(
        [
            ("planned", "Planned"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("postponed", "Postponed"),
        ],
        string="Visit Status",
        default="planned",
        tracking=True,
    )

    cancel_reason = fields.Text(string="Cancellation Reason", tracking=True)
    postpone_reason = fields.Text(string="Postpone Reason", tracking=True)

    # =====================================================
    # MEETING DETAILS
    # =====================================================

    person_met = fields.Char(string="Name of Person Met")
    designation = fields.Char(string="Designation")
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")

    decision_maker = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Decision Maker",
    )

    current_equipment = fields.Char(
        string="Current Equipment (Vendor/Model)"
    )

    notes = fields.Text(string="Notes")

    # =====================================================
    # OPPORTUNITIES
    # =====================================================

    opportunity_ids = fields.One2many(
        "sales.visit.opportunity",
        "visit_id",
        string="Opportunities",
    )

    # =====================================================
    # CALENDAR INTEGRATION
    # =====================================================

    calendar_event_id = fields.Many2one(
        "calendar.event",
        string="Related Meeting",
        readonly=True,
        copy=False,
    )

    # =====================================================
    # CRM & HELPDESK INTEGRATION
    # =====================================================

    lead_id = fields.Many2one(
        "crm.lead",
        string="Related Lead",
        readonly=True,
        copy=False,
    )

    ticket_id = fields.Many2one(
        "helpdesk.ticket",
        string="Related Ticket",
        readonly=True,
        copy=False,
    )

    # =====================================================
    # CREATE
    # =====================================================

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("sales.visit") or "New"

        record = super().create(vals)
        record._create_or_update_calendar_event()
        return record

    # =====================================================
    # WRITE (SYNC CHANGES)
    # =====================================================

    def write(self, vals):
        result = super().write(vals)

        for record in self:
            if any(field in vals for field in [
                "plan_date", "sales_rep_id",
                "facility_id", "objective", "region"
            ]):
                record._create_or_update_calendar_event()

        return result

    # =====================================================
    # DELETE
    # =====================================================

    def unlink(self):
        for record in self:
            if record.calendar_event_id:
                record.calendar_event_id.unlink()
        return super().unlink()

    # =====================================================
    # WORKFLOW BUTTONS
    # =====================================================

    def action_complete(self):
        self.write({"visit_status": "completed"})

    def action_cancel(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Cancel Visit",
            "res_model": "sales.visit.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visit_id": self.id},
        }

    def action_postpone(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Postpone Visit",
            "res_model": "sales.visit.postpone.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visit_id": self.id},
        }

    # =====================================================
    # CREATE LEAD (MANUAL)
    # =====================================================

    def action_create_lead(self):
        self.ensure_one()

        if self.lead_id:
            return

        lead = self.env["crm.lead"].create({
            "name": f"Lead from Visit - {self.name}",
            "partner_id": self.facility_id.id if self.facility_id else False,
            "contact_name": self.person_met,
            "phone": self.phone,
            "email_from": self.email,
            "description": self.notes,
            "user_id": self.sales_rep_id.id,
        })

        self.lead_id = lead.id

    def action_view_lead(self):
        self.ensure_one()

        if not self.lead_id:
            return

        return {
            "type": "ir.actions.act_window",
            "name": "Related Lead",
            "res_model": "crm.lead",
            "view_mode": "form",
            "res_id": self.lead_id.id,
            "target": "current",
        }

    # =====================================================
    # CREATE HELPDESK TICKET (MANUAL)
    # =====================================================

    def action_create_ticket(self):
        self.ensure_one()

        if self.ticket_id:
            return

        ticket = self.env["helpdesk.ticket"].create({
            "name": f"Ticket from Visit - {self.name}",
            "partner_id": self.facility_id.id if self.facility_id else False,
            "description": self.notes,
            "user_id": self.sales_rep_id.id,
        })

        self.ticket_id = ticket.id

    def action_view_ticket(self):
        self.ensure_one()

        if not self.ticket_id:
            return

        return {
            "type": "ir.actions.act_window",
            "name": "Related Ticket",
            "res_model": "helpdesk.ticket",
            "view_mode": "form",
            "res_id": self.ticket_id.id,
            "target": "current",
        }

    # =====================================================
    # OPEN CALENDAR
    # =====================================================

    def action_view_calendar(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Meetings",
            "res_model": "calendar.event",
            "view_mode": "calendar,tree,form",
            "domain": [("id", "=", self.calendar_event_id.id)],
        }

    # =====================================================
    # INTERNAL METHOD - CALENDAR SYNC
    # =====================================================

    def _create_or_update_calendar_event(self):
        for record in self:
            if not record.plan_date:
                return

            start_datetime = fields.Datetime.to_datetime(record.plan_date)
            stop_datetime = start_datetime + timedelta(hours=1)

            description = f"""
Facility: {record.facility_id.name if record.facility_id else ''}
Objective: {record.objective or ''}
Region: {record.region or ''}
            """

            if record.calendar_event_id:
                record.calendar_event_id.write({
                    "name": f"Sales Visit - {record.name}",
                    "start": start_datetime,
                    "stop": stop_datetime,
                    "user_id": record.sales_rep_id.id,
                    "description": description,
                })
            else:
                event = self.env["calendar.event"].create({
                    "name": f"Sales Visit - {record.name}",
                    "start": start_datetime,
                    "stop": stop_datetime,
                    "user_id": record.sales_rep_id.id,
                    "description": description,
                })
                record.calendar_event_id = event.id


class SalesVisitOpportunity(models.Model):
    _name = "sales.visit.opportunity"
    _description = "Sales Visit Opportunity Line"

    visit_id = fields.Many2one(
        "sales.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
    )

    name = fields.Char(string="Opportunity", required=True)

    opportunity_type = fields.Selection(
        [
            ("replacement", "Replacement"),
            ("new_purchase", "New Purchase"),
            ("service_contract", "Service Contract"),
            ("consumables", "Consumables"),
        ],
        string="Opportunity Type",
    )

    budget = fields.Float(string="Budget (USD/TZS)")

    source_of_funds = fields.Char(string="Source of Funds")

    execution_method = fields.Selection(
        [
            ("tender", "Tender"),
            ("placement", "Placement"),
            ("direct_purchase", "Direct Purchase"),
        ],
        string="Opportunity Execution Method",
    )

    challenges_remarks = fields.Text(string="Challenges/Remarks")

    support_needed = fields.Text(string="Support Needed")

    action_points = fields.Text(string="Action Points")

    next_followup_date = fields.Date(string="Next Follow-up Date")

    followup_method = fields.Selection(
        [
            ("call", "Call"),
            ("email", "Email"),
            ("visit", "Visit"),
            ("demo", "Demo"),
        ],
        string="Follow-up Method",
    )

    expected_closing_date = fields.Date(string="Expected Closing Date")

    deal_value = fields.Float(string="Deal Value (TZS)")

    lead_status = fields.Selection(
        [
            ("open", "Open"),
            ("negotiation", "Negotiation"),
            ("won", "Won"),
            ("lost", "Lost"),
        ],
        string="Lead Status",
    )