from odoo import models, fields

class EquipmentTicketHistory(models.Model):
    _name = 'equipment.ticket.history'
    _description = 'Equipment Ticket History'

    equipment_tracking_id = fields.Many2one(
        'equipment.tracking',
        string="Equipment",
        ondelete='cascade'
    )

    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string="Ticket"
    )

    ticket_name = fields.Char(
        related='ticket_id.name',
        store=True
    )

    closed_date = fields.Datetime(
        string="Closed Date"
    )

    stage_name = fields.Char(
        string="Stage"
    )

    description = fields.Text(
        string="Resolution Notes"
    )