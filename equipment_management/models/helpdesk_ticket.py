from odoo import models, fields, api

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    equipment_tracking_id = fields.Many2one(
        'equipment.tracking',
        string="Equipment"
    )

    equipment_serial = fields.Char(
        string="Serial Number",
        related="equipment_tracking_id.serial_number",
        readonly=True
    )

    equipment_model_id = fields.Many2one(
        'equipment.model',
        string="Model",
        related="equipment_tracking_id.model_id",
        readonly=True
    )

    manufacturer_id = fields.Many2one(
        'equipment.manufacturer',
        string="Manufacturer",
        related="equipment_tracking_id.manufacturer_id",
        readonly=True
    )
    reagent_batch = fields.Char(string="Reagent Batch")
    software = fields.Char(string="Software Version")
    complainer = fields.Char(string="Complainer")
    customer_followup = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Customer Follow-Up", required=True)
    initial_troubleshoot = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Initial Troubleshoot")

    troubleshoot_explanation = fields.Text(
        string="Troubleshoot Explanation"
    )
    incident = fields.Char(string="Incident")


    def _default_capa_template(self):
        return """
        <h3>Input for Corrective/Preventive Action</h3>

        <p><b>Ref.:</b> Complaint ticket no</p>
        <p><b>Description of issue triggering the CAPA:</b><br/><br/></p>

        <h4>Scope</h4>
        <p>CAPA related to product or quality system?</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>

        <h4>Root Cause / Investigation</h4>
        <p><b>Error Analysis:</b> (e.g. fishbone analysis or 5 why)</p>
        <p>-</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>

        <h4>Risk Assessment</h4>
        <p>Risk and Impact assessment:</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>

        <h4>Immediate Correction</h4>
        <p>Describe the immediate actions taken:</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>

        <h4>Corrective / Preventive Action</h4>
        <p>Responsible: ____________</p>
        <p>Description of action plan:</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>

        <h4>Verification of CAPA</h4>
        <p>Responsible for verification:</p>
        <p>Verification method:</p>
        <p>Date: ____________ &nbsp;&nbsp;&nbsp; Completed by: ____________</p>
      
      """

    
    capa_template = fields.Html(
            string="CAPA Form",
            default=_default_capa_template
        )

    def write(self, vals):
        res = super().write(vals)

        if 'stage_id' in vals:
            for rec in self:
                if rec.stage_id.name == 'Solved' and rec.equipment_tracking_id:

                    existing = self.env['equipment.ticket.history'].search([
                        ('ticket_id', '=', rec.id)
                    ], limit=1)

                    if not existing:
                        self.env['equipment.ticket.history'].create({
                            'equipment_tracking_id': rec.equipment_tracking_id.id,
                            'ticket_id': rec.id,
                            'closed_date': fields.Datetime.now(),
                            'stage_name': rec.stage_id.name,
                            'description': rec.description,
                        })

        return res
        