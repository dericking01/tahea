# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class EquipmentManagement(models.Model):
    _name = 'equipment.management'
    _description = 'Equipment Management'

    name = fields.Char(string="Equipment Name", required=True)
    serial_number = fields.Char(string="Serial Number")

    model_id = fields.Many2one(
        'equipment.model',
        string="Model"
    )

    manufacturer_id = fields.Many2one(
        'equipment.manufacturer',
        string="Manufacturer",
        related='model_id.manufacturer_id',
        store=True,
        readonly=True
    )

    _sql_constraints = [
        ('unique_serial_number',
         'unique(serial_number)',
         'The Serial Number must be unique!')
    ]
   

class EquipmentManufacturer(models.Model):
    _name = 'equipment.manufacturer'
    _description = 'Equipment Manufacturer'

    name = fields.Char(string="Manufacturer Name", required=True)

class EquipmentModel(models.Model):
    _name = 'equipment.model'
    _description = 'Equipment Model'

    name = fields.Char(string="Model Name", required=True)
    manufacturer_id = fields.Many2one(
        'equipment.manufacturer',
        string="Manufacturer"
    )

# ===============================
# EQUIPMENT TRACKING
# ===============================
class EquipmentTracking(models.Model):
    _name = 'equipment.tracking'
    _description = 'Equipment Tracking'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char(
        string="Tracking Reference",
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )
    equipment_id = fields.Many2one(
        'equipment.management',
        string="Equipment",
    )

    equipment_name = fields.Char(
        string="Equipment Name",
        related="equipment_id.name",
        store=True,
        readonly=True
    )

    serial_number = fields.Char(
        string="Serial Number",
        related="equipment_id.serial_number",
        store=True,
        readonly=True
    )

    model_id = fields.Many2one(
        'equipment.model',
        string="Model",
        related="equipment_id.model_id",
        store=True,
        readonly=True
    )

    manufacturer_id = fields.Many2one(
        'equipment.manufacturer',
        string="Manufacturer",
        related="equipment_id.manufacturer_id",
        store=True,
        readonly=True
    )

    customer_id = fields.Many2one(
        'res.partner',
        string="Customer"
    )

    region_id = fields.Many2one(
        'equipment.region',
        string="Region"
    )

    district = fields.Char(string="District")

    user_contact_name = fields.Char(string="User Contact Name")
    user_contact_number = fields.Char(string="User Contact Number")
    user_email = fields.Char(string="User Email")

    business_model = fields.Selection([
        ('placement', 'Placement'),
        ('sold', 'Sold')
    ], string="Business Model")
    ticket_history_ids = fields.One2many('equipment.ticket.history','equipment_tracking_id',
    string="Ticket History")

    installation_date = fields.Date(string="Installation Date")
    training_date = fields.Date(string="Application/User Training Date")

    engineer_name = fields.Char(string="Engineer Name")
    specialist_name = fields.Char(string="Application Specialist")
    encore_assigned = fields.Char(string="BDE Name")
    attachment_training = fields.Many2many('ir.attachment', string="Training & Installation Attachments")
   

    warranty_months = fields.Integer(string="Warranty Period (Months)")

    warranty_expiry_date = fields.Date(
        string="Warranty Expiry Date",
        compute="_compute_warranty_expiry",
        store=True
    )

    warranty_status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired')
    ], string="Warranty Status",
       compute="_compute_warranty_status",
       store=True)

    last_ppm_date = fields.Date(string="Last PPM Date")

    next_ppm_months = fields.Integer(string="Next PPM After (Months)")

    next_ppm_date = fields.Date(
        string="Next PPM Date",
        compute="_compute_next_ppm",
        store=True
    )

    ppm_status = fields.Selection([
        ('due', 'Due'),
        ('overdue', 'Overdue'),
        ('ok', 'OK')
    ], string="PPM Status",
       compute="_compute_ppm_status",
       store=True)
    
    ticket_count = fields.Integer(compute="_compute_ticket_count")

    def _compute_ticket_count(self):
        for rec in self:
            rec.ticket_count = self.env['helpdesk.ticket'].search_count([
                ('equipment_tracking_id', '=', rec.id)
            ])

    def action_create_ticket(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Service Ticket',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.customer_id.id,
                'default_equipment_tracking_id': self.id,
                'default_name': f"Service Request - {self.equipment_name}",
                'default_description': f"""
    Equipment: {self.equipment_name}
    Serial: {self.serial_number}
    Model: {self.model_id.name if self.model_id else ''}

    Issue:
    """,
            }
        }
    
    sale_order_count = fields.Integer(
        string="Sales Orders",
        compute='_compute_sale_order_count'
    )

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = self.env['sale.order'].search_count([('equipment_id', '=', rec.id)])

    def action_view_sales_orders(self):
        self.ensure_one()
        return {
            'name': 'Sales Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('equipment_id','=',self.id)],
            'context': {'default_equipment_id': self.id},
        }

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'list,form',
            'domain': [('equipment_tracking_id', '=', self.id)],
            'context': {'default_equipment_tracking_id': self.id},
        }

    def action_create_sales_order(self):
        self.ensure_one()
        if not self.customer_id:
            raise UserError("Please select a customer before creating a Sales Order.")

        return {
            'name': 'Create Sales Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',  # open as popup
            'context': {
                'default_partner_id': self.customer_id.id,
                'default_equipment_id': self.id,  # optional custom field
            }
        }


    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('equipment.tracking') or 'New'
        return super().create(vals)

    # ===============================
    # COMPUTE METHODS
    # ===============================

    @api.depends('installation_date', 'warranty_months')
    def _compute_warranty_expiry(self):
        for rec in self:
            if rec.installation_date and rec.warranty_months:
                rec.warranty_expiry_date = rec.installation_date + relativedelta(months=rec.warranty_months)
            else:
                rec.warranty_expiry_date = False

    @api.depends('warranty_expiry_date')
    def _compute_warranty_status(self):
        today = fields.Date.today()
        for rec in self:
            if rec.warranty_expiry_date:
                rec.warranty_status = 'active' if rec.warranty_expiry_date >= today else 'expired'
            else:
                rec.warranty_status = False

    @api.depends('last_ppm_date', 'next_ppm_months')
    def _compute_next_ppm(self):
        for rec in self:
            if rec.last_ppm_date and rec.next_ppm_months:
                rec.next_ppm_date = rec.last_ppm_date + timedelta(days=30 * rec.next_ppm_months)
            else:
                rec.next_ppm_date = False

    @api.depends('next_ppm_date')
    def _compute_ppm_status(self):
        today = fields.Date.today()
        for rec in self:
            if rec.next_ppm_date:
                if rec.next_ppm_date < today:
                    rec.ppm_status = 'overdue'
                elif rec.next_ppm_date == today:
                    rec.ppm_status = 'due'
                else:
                    rec.ppm_status = 'ok'
            else:
                rec.ppm_status = False


class EquipmentRegion(models.Model):
    _name = 'equipment.region'
    _description = 'Region'

    name = fields.Char(string="Region Name", required=True)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    equipment_id = fields.Many2one(
        'equipment.tracking',
        string="Equipment"
    )