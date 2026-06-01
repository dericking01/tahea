# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportBooking(models.Model):
    _name = "fleet.transport.booking"
    _description = "Fleet Transport Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Reference",
        default="New",
        readonly=True,
        copy=False,
    )

    booking_date = fields.Datetime(
        string="Start Date",
        required=True,
        tracking=True,
    )

    end_date = fields.Datetime(
        string="End Date",
        required=True,
        tracking=True,
    )

    from_location = fields.Char(string="From")
    to_location = fields.Char(string="To")
    purpose = fields.Text(string="Purpose")

    state = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ], default="draft", tracking=True)

    line_ids = fields.One2many(
        "fleet.transport.booking.line",
        "booking_id",
        string="Vehicles",
    )

    # -------------------------
    # SEQUENCE
    # -------------------------
    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "fleet.transport.booking"
            ) or "New"
        return super().create(vals)

    # -------------------------
    # WORKFLOW BUTTONS
    # -------------------------
    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError("Please add at least one vehicle to the booking.")

            for line in rec.line_ids:
                # Prevent vehicle under maintenance
                maintenance = self.env["internal.job.order"].search([
                    ("vehicle_id", "=", line.vehicle_id.id),
                    ("state", "=", "in_progress")
                ], limit=1)
                if maintenance:
                    raise ValidationError(
                        f"Vehicle {line.vehicle_id.name} is under maintenance."
                    )

                # Prevent double booking
                conflict = self.search([
                    ("line_ids.vehicle_id", "=", line.vehicle_id.id),
                    ("state", "in", ["approved", "confirmed", "in_progress"]),
                    ("id", "!=", rec.id),
                ], limit=1)
                if conflict:
                    raise ValidationError(
                        f"Vehicle {line.vehicle_id.name} is already booked."
                    )

            rec.write({"state": "confirmed"})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class TransportBookingLine(models.Model):
    _name = "fleet.transport.booking.line"
    _description = "Vehicles in Transport Booking"

    booking_id = fields.Many2one(
        "fleet.transport.booking",
        string="Booking Reference",
        required=True,
        ondelete="cascade"
    )
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        required=True,
        tracking=True
    )
    notes = fields.Text(string="Notes")