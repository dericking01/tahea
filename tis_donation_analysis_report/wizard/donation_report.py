# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2022. All rights reserved.
import datetime
import json
import logging
_logger = logging.getLogger(__name__)
from odoo import fields, models, api
from datetime import timedelta, date


class DonationReport(models.TransientModel):
    _name = 'donation.report.create'

    from_date = fields.Date(string="From date",  default=date.today(), tracking=True)
    to_date = fields.Date(string="To date", default=date.today(), tracking=True)
    based_on = fields.Selection([
        ('donor', 'Donor'), 
        ('project', 'Project')
        ], string="Based on", required=True, default='donor')
    project_based = fields.Many2one('project.project', 'Projects')
    donor_based = fields.Many2many('res.partner',string="Donors")

    def print_pnl_pdf_report(self):
        data = {}
        data['form'] = {}
        data['form'].update(self.read([])[0])
        return self.env.ref('tis_donation_analysis_report.pdf_donation_report').with_context(
            landscape=True).report_action(self, data=data)

    # def print_report(self):
    #     total_list = []
    #     com_list = []
    #     date_list = []
    #     p_total = 0

    #     _logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')

    #     if not (self.to_date and self.from_date):
    #         sdate = date(date.today().year, 1, 1)
    #         edate = date(date.today().year, 12, 31)

    #         def daterange(date1, date2):
    #             for n in range(int((date2 - date1).days) + 1):
    #                 yield date1 + timedelta(n)

    #         start_dt = sdate
    #         end_dt = edate
    #         for dt in daterange(start_dt, end_dt):
    #             date_list.append(dt.strftime("%Y-%m-%d"))
    #         date1 =str(sdate)
    #         date2 =str(edate)
    #         donors = self.env['res.partner'].search([('customer_rank', '=', 1)])
    #         list_new = []
    #         for r in donors:
    #             if r.donation_ids:
    #                 list = []
    #                 d_total = 0
    #                 don1 = {'name': r.name, }
    #                 for rec in r.donation_ids:
    #                     if str(rec.donation_date) in date_list:
    #                         donrs = {
    #                             'number': rec.number,
    #                             'date': str(rec.donation_date),
    #                             'payment': rec.payment_ref,
    #                             'project': rec.project_id.name,
    #                             'analytic_account_id': rec.line_ids.analytic_account_id.id,
    #                             'analytic_account_name': rec.line_ids.analytic_account_id.name,
    #                             'amount': rec.amount_total,
    #                             'journal_entry': rec.move_id.ref,
    #                             'journal_name': rec.journal_id.name,
    #                         }
    #                         list.append(donrs)
    #                 don1.update({'list': list})
    #                 list_new.append(don1)
    #         projects = self.env['project.project'].search([])
    #         plist = []

    #         for p in projects:
    #             donations = self.env['donation.donation'].search([('project_id', '=', p.id)])
    #             dlist = []
    #             for d in donations:
    #                 if str(d.donation_date) in date_list:
    #                     donrs = {
    #                         'number': d.number,
    #                         'date': str(d.donation_date),
    #                         'payment': d.payment_ref,
    #                         'project': d.project_id.name,
    #                         'analytic_account_id': d.line_ids.analytic_account_id.id,
    #                         'analytic_account_name': d.line_ids.analytic_account_id.name,
    #                         'amount': d.amount_total,
    #                         'journal_entry': d.move_id.ref,
    #                         'journal_name': d.journal_id.name,
    #                     }
    #                     p_total = p_total + d.amount_total
    #                     print('p_total', p_total)
    #                     dlist.append(donrs)
    #             prjct = {'pname': p.name, 'donations': dlist}

    #             plist.append(prjct)

    #         company = self.env.company
    #         co = {
    #             'id': company.id,
    #             'name': company.name
    #         }
    #         com_list.append(co)
    #         com_dict_tot = {
    #             "company": com_list
    #         }
    #         total_list.append(com_dict_tot)


    #         data = {
    #             'amount_total': p_total,
    #             'donors': list_new,
    #             'projects': plist,
    #             'company': total_list[0]['company'],
    #             'to_date': date2,
    #             'from_date': date1,
    #             'based_on': self.based_on,
    #         }
    #         print('c', data)


    #     else:
    #         def daterange(date1, date2):
    #             for n in range(int((date2 - date1).days) + 1):
    #                 yield date1 + timedelta(n)

    #         start_dt = self.from_date
    #         end_dt = self.to_date
    #         for dt in daterange(start_dt, end_dt):
    #             date_list.append(dt.strftime("%Y-%m-%d"))

    #         donors = self.env['res.partner'].search([('customer_rank', '=', 1)])
    #         list_new = []
    #         for r in donors:
    #             if r.donation_ids:
    #                 list = []
    #                 d_total=0
    #                 don1 = {'name': r.name, }
    #                 for rec in r.donation_ids:
    #                     if str(rec.donation_date) in date_list:
    #                         donrs = {
    #                             'number': rec.number,
    #                             'date': str(rec.donation_date),
    #                             'payment': rec.payment_ref,
    #                             'project': rec.project_id.name,
    #                             'analytic_account_id': rec.line_ids.analytic_account_id.id,
    #                             'analytic_account_name': rec.line_ids.analytic_account_id.name,
    #                             'amount': rec.amount_total,
    #                             'journal_entry': rec.move_id.ref,
    #                             'journal_name': rec.journal_id.name,
    #                         }
    #                         list.append(donrs)
    #                 don1.update({'list': list})
    #                 list_new.append(don1)
    #         projects = self.env['project.project'].search([])
    #         plist = []

    #         for p in projects:
    #             donations = self.env['donation.donation'].search([('project_id', '=', p.id)])
    #             dlist = []
    #             for d in donations:
    #                 if str(d.donation_date) in date_list:
    #                     donrs = {
    #                         'number': d.number,
    #                         'date': str(d.donation_date),
    #                         'payment': d.payment_ref,
    #                         'project': d.project_id.name,
    #                         'analytic_account_id': d.line_ids.analytic_account_id.id,
    #                         'analytic_account_name': d.line_ids.analytic_account_id.name,
    #                         'amount': d.amount_total,
    #                         'journal_entry': d.move_id.ref,
    #                         'journal_name': d.journal_id.name,
    #                     }
    #                     p_total = p_total+ d.amount_total
    #                     print('p_total',p_total)
    #                     dlist.append(donrs)
    #             prjct = {'pname': p.name, 'donations': dlist}

    #             plist.append(prjct)

    #         company = self.env.company
    #         co = {
    #             'id': company.id,
    #             'name': company.name
    #         }
    #         com_list.append(co)
    #         com_dict_tot = {
    #             "company": com_list
    #         }
    #         total_list.append(com_dict_tot)

    #         date1 = str(self.to_date)
    #         date2 = str(self.from_date)
    #         data = {
    #             'amount_total': p_total,
    #             'donors': list_new,
    #             'projects': plist,
    #             'company': total_list[0]['company'],
    #             'to_date': date1,
    #             'from_date': date2,
    #             'based_on': self.based_on,
    #         }
    #         print('c', data)


    #     return self.env.ref('tis_donation_analysis_report.pdf_donation_report').report_action(self, data=data)
