# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2022. All rights reserved.

import datetime
import logging
from odoo import api, models, _
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)
from num2words import num2words

class DonationLine(models.Model):
    _inherit = "donation.line"

    @api.onchange("product_id")
    def product_id_change(self):
        for line in self:
            line.analytic_account_id = self.donation_id.project_id.analytic_account_id.id



class ReportRender(models.AbstractModel):
    _name = 'report.tis_donation_analysis_report.donation_report_pdf'
    _description = 'Product profit Report Render'

    @api.model
    def _get_report_values(self, docids, data=None):
        # only for pdf report
        model_data = data['form']
        return self.generate_report_values(model_data)

    @api.model
    def generate_report_values(self, data):
        from_date = data['from_date']
        to_date = data['to_date']

        donor_based = data['donor_based']
        project_based = data['project_based']
        sum_amount = 0
        # company = data['company']
        if donor_based:
            donations = self.env['donation.donation'].search([('donation_date', '>=', from_date), ('donation_date', '<=', to_date),('state', 'not in', ['draft']),('partner_id', 'in', donor_based)])
            if not donations:
                raise ValidationError("There is no donations with donors in this date range please select some other dates !!!!")
            sum_amount = 0
            for donation in donations:
                sum_amount += int(donation.amount_total) 
        if project_based:
            # project = self.env['project.project'].search([('name','=', project_based)])
            # _logger.info(project)
            donations = self.env['donation.donation'].search([('donation_date', '>=', from_date), ('donation_date', '<=', to_date),('state', 'not in', ['draft']),('project_id', '=', project_based[0])])
            if not donations:
                raise ValidationError("There is no donations with projects in this date range please select some other dates !!!!")
            sum_amount = 0
            for donation in donations:
                sum_amount += int(donation.amount_total)   

        return {
            'data': data,
            'total_amount':sum_amount,
            'donations' : donations,
            'report_date': datetime.datetime.now().strftime("%Y-%m-%d"),
        }

class DonationDonation(models.Model):
    _inherit = "donation.donation"
    
    @api.depends('state')
    def write(self, vals):
        res = super(DonationDonation, self).write(vals)
        for rec in self.line_ids:
            rec.analytic_account_id = self.project_id.analytic_account_id.id
        return res

    @api.model
    def create(self, vals):
        res = super(DonationDonation, self).create(vals)
        for rec in res.line_ids:
            rec.analytic_account_id = res.project_id.analytic_account_id.id
        return res
