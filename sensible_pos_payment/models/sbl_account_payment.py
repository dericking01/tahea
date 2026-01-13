# Powered by Sensible Consulting Services
# -*- coding: utf-8 -*-
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
import base64

from odoo import models
from markupsafe import Markup


class SblAccountPayment(models.Model):
    _inherit = 'account.payment'

    def sbl_get_payment_receipt_data(self):
        """Get all payment data required for receipt in one call"""
        self.ensure_one()
        
        # Get company data
        company_data = {
            'id': self.company_id.id,
            'name': self.company_id.name,
            'email': self.company_id.email,
            'phone': self.company_id.phone,
            'website': self.company_id.website,
        }
        
        # Get partner data if exists
        partner_data = None
        if self.partner_id:
            partner_data = [self.partner_id.id, self.partner_id.name]
        
        # Get journal data if exists
        journal_data = None
        if self.journal_id:
            journal_data = [self.journal_id.id, self.journal_id.name]
        
        # Get currency data
        currency_data = {'id': self.currency_id.id, 'name': self.currency_id.name}
        
        # Check if payment is related to an invoice
        invoice_data = None
        if self.reconciled_invoice_ids:
            invoice = self.reconciled_invoice_ids[0]  # Get first invoice
            invoice_data = {
                'number': invoice.name,
                'date': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else None,
                'total': invoice.amount_total,
                'state': invoice.state
            }
        
        return {
            'payment': {
                'id': self.id,
                'display_name': self.display_name,
                'company_id': [self.company_id.id, self.company_id.name],
                'partner_id': partner_data,
                'amount': self.amount,
                'currency_id': [self.currency_id.id, self.currency_id.name],
                'journal_id': journal_data,
                'memo': self.memo or '',
                'currency': currency_data,
                'invoice': invoice_data,
            },
            'company_data': {
                'company': company_data,
                'header': '',  # Can be configured if needed
                'cashier': self.env.user.name,
            }
        }


    def _sbl_prepare_mail_values(self, email, ticket):
        message = Markup(
            self.env._("<p>Dear %(client_name)s,<br/>Here is your Payment Receipt %(payment_receipt)s for \
            amounting in %(amount)s from %(company_name)s. </p>")
        ) % {
            'client_name': self.partner_id.name or self.env._('Customer'),
            'payment_receipt': self.display_name,
            'amount': self.currency_id.format(self.amount),
            'company_name': self.company_id.name,
        }

        return {
            'subject': self.env._('Payment Receipt %s', self.display_name),
            'body_html': message,
            'author_id': self.env.user.partner_id.id,
            'email_from': self.env.company.email or self.env.user.email_formatted,
            'email_to': email,
            'attachment_ids': self._sbl_add_mail_attachment(self.display_name, ticket),
        }
    
    def _sbl_add_mail_attachment(self, name, ticket):
        attachment = []
        filename = 'Payment Receipt-' + name + '.jpg'
        receipt = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': ticket,
            'res_model': 'pos.order',
            'res_id': self.ids[0],
            'mimetype': 'image/jpeg',
        })
        attachment += [(4, receipt.id)]

        # if self.mapped('account_move'):
        #     report = self.env['ir.actions.report']._render_qweb_pdf("account.account_invoices", self.account_move.ids[0])
        #     filename = name + '.pdf'
        #     invoice = self.env['ir.attachment'].create({
        #         'name': filename,
        #         'type': 'binary',
        #         'datas': base64.b64encode(report[0]),
        #         'res_model': 'pos.order',
        #         'res_id': self.ids[0],
        #         'mimetype': 'application/x-pdf'
        #     })
        #     attachment += [(4, invoice.id)]

        return attachment
    
    def sbl_action_send_receipt(self, email, ticket_image):
        self.env['mail.mail'].sudo().create(self._sbl_prepare_mail_values(email, ticket_image)).send()