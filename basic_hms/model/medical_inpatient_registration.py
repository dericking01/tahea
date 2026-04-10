# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from datetime import date,datetime

class medical_inpatient_registration(models.Model):
    _name = 'medical.inpatient.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = 'Medical Inpatient Registration'

    name = fields.Char(string="Registration Code", copy=False, readonly=True, index=True)
    patient_id = fields.Many2one('medical.patient',string="Patient",required=True)
    hospitalization_date = fields.Datetime(string="Hospitalization date",required=True)
    discharge_date = fields.Datetime(string="Expected Discharge date",required=False)
    attending_physician_id = fields.Many2one('medical.physician',string="Attending Physician")
    operating_physician_id = fields.Many2one('medical.physician',string="Operating Physician")
    admission_type = fields.Selection([('routine','Routine'),('maternity','Maternity'),('medical','Medical'),('surgical','Surgical')],required=True,string="Admission Type")
    medical_pathology_id = fields.Many2one('medical.pathology',string="Reason for Admission")
    info = fields.Text(string="Doctor Info")
    bed_transfers_ids = fields.One2many('bed.transfer','inpatient_id',string='Transfer Bed')
    medical_diet_belief_id = fields.Many2one('medical.diet.belief',string='Belief')
    therapeutic_diets_ids = fields.One2many('medical.inpatient.diet','medical_inpatient_registration_id',string='Therapeutic_diets')
    diet_vegetarian = fields.Selection([('none','None'),('vegetarian','Vegetarian'),('lacto','Lacto Vegetarian'),('lactoovo','Lacto-Ovo-Vegetarian'),('pescetarian','Pescetarian'),('vegan','Vegan')],string="Vegetarian")
    nutrition_notes = fields.Text(string="Nutrition notes / Directions")
    state = fields.Selection([('free','Free'),('confirmed','Confirmed'),('hospitalized','Hospitalized'),('cancel','Cancel'),('done','Done')],string="State",default="free")
    nursing_plan = fields.Text(string="Nursing Plan")
    discharge_plan = fields.Text(string="Discharge Plan")
    icu = fields.Boolean(string="ICU")
    medication_ids = fields.One2many('medical.inpatient.medication','medical_inpatient_registration_id',string='Medication')
    bed_no = fields.Char(string="Bed No")
    room_no = fields.Char(string="Room No")
    no_day = fields.Char(string="No Of Days")
    item_line_ids = fields.One2many('medical.item.line', 'hospitalization_id', string='Items Lines')
    log_line_ids = fields.One2many('medical.log.line', 'hospitalization_id', string='Medical log Line')
    note = fields.Text(string="Note")

    @api.model
    def default_get(self, fields):
        result = super(medical_inpatient_registration, self).default_get(fields)
        patient_id  = self.env['ir.sequence'].next_by_code('medical.inpatient.registration')
        if patient_id:
            result.update({
                        'name':patient_id,
                       })
        return result

    def registration_confirm(self):
        self.write({'state': 'confirmed'})

    def registration_admission(self):
        self.write({'state': 'hospitalized'})

    def registration_cancel(self):
        self.write({'state': 'cancel'})

    def patient_discharge(self):
        self.write({'state': 'done'})
class ItemUsage(models.Model):
    _name = "medical.item.line"
    _description = "Consumable Items"

    name = fields.Char(string="Label")
    product_id = fields.Many2one("product.template", string='Item')
    qty = fields.Float(string="Qty")
    hospitalization_id = fields.Many2one("medical.inpatient.registration")

class MedicalCharts(models.Model):
    _name = "medical.log.line"
    _description = "Medication Log"

    name = fields.Char(string="Label")
    date = fields.Datetime(string='Date')
    freuency_route = fields.Char(string="Frequency Route")
    doctor_id = fields.Many2one('medical.physician')
    hospitalization_id = fields.Many2one("medical.inpatient.registration")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:s
