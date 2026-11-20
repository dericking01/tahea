# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    """Leasing pipeline on native CRM: enquiry -> prospect -> viewing -> application
    -> screening -> offer (draft lease). Approval, signature, occupancy and billing
    continue on the lease."""
    _inherit = 'crm.lead'

    re_is_rental = fields.Boolean('Rental Prospect', index=True)
    re_property_id = fields.Many2one('re.property', 'Property of Interest')
    re_unit_ids = fields.Many2many('re.unit', 'crm_lead_re_unit_rel', 'lead_id', 'unit_id', string='Units of Interest',
                                   domain="[('property_id', '=', re_property_id), ('rental_status', '=', 'available')]")
    re_lease_type_id = fields.Many2one('re.lease.type', 'Lease Type')
    re_budget_monthly = fields.Monetary('Monthly Budget', currency_field='company_currency')
    re_move_in_date = fields.Date('Desired Move-in')
    re_term_months = fields.Integer('Desired Term (months)', default=12)
    re_viewing_date = fields.Datetime('Viewing Appointment')
    re_viewing_done = fields.Boolean('Viewing Completed')
    re_application_date = fields.Date('Application Submitted')
    re_screening_state = fields.Selection([
        ('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('passed', 'Passed'),
        ('conditional', 'Passed with Conditions'), ('failed', 'Failed')], default='not_started', tracking=True)
    re_screening_notes = fields.Text('Screening Notes (references, income, ID verification)')
    re_proposed_rent = fields.Monetary('Offered Monthly Rent', currency_field='company_currency')
    re_lease_id = fields.Many2one('re.lease', 'Lease Offer', copy=False, readonly=True)

    @api.onchange('re_unit_ids')
    def _onchange_re_units(self):
        if self.re_unit_ids and not self.re_proposed_rent:
            self.re_proposed_rent = sum(self.re_unit_ids.mapped('market_rent'))

    def action_re_submit_application(self):
        self.write({'re_application_date': fields.Date.context_today(self), 're_screening_state': 'in_progress'})

    def action_re_create_lease(self):
        self.ensure_one()
        if self.re_lease_id:
            raise UserError(_('A lease offer already exists for this opportunity.'))
        if self.re_screening_state not in ('passed', 'conditional'):
            raise UserError(_('Complete tenant screening before preparing a lease offer.'))
        if not self.re_unit_ids:
            raise UserError(_('Select the unit(s) of interest.'))
        if not self.partner_id:
            self._handle_partner_assignment(create_missing=True)
        partner = self.partner_id
        if not partner:
            raise UserError(_('Set the prospect contact first.'))
        lease_type = self.re_lease_type_id or self.env['re.lease.type'].search([], limit=1)
        start = self.re_move_in_date or fields.Date.context_today(self)
        lease = self.env['re.lease'].create({
            'tenant_id': partner.id, 'property_id': self.re_property_id.id or self.re_unit_ids[:1].property_id.id,
            'building_id': self.re_unit_ids[:1].building_id.id, 'unit_ids': [(6, 0, self.re_unit_ids.ids)],
            'lease_type_id': lease_type.id, 'date_start': start,
            'date_end': start + relativedelta(months=self.re_term_months or 12, days=-1),
            'rent_amount': self.re_proposed_rent or sum(self.re_unit_ids.mapped('market_rent')),
            'deposit_amount': (self.re_proposed_rent or 0.0) * (lease_type.default_deposit_months or 0.0),
            'billing_frequency': lease_type.default_billing_frequency or 'monthly',
            'notice_period_days': lease_type.default_notice_days or 90,
            'user_id': self.user_id.id or self.env.uid, 'crm_lead_id': self.id,
        })
        self.re_lease_id = lease
        self.message_post(body=_('Lease offer %s prepared.', lease.name))
        return {'type': 'ir.actions.act_window', 'res_model': 're.lease', 'res_id': lease.id, 'view_mode': 'form'}
