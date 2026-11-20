# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RePortfolio(models.Model):
    _name = 're.portfolio'
    _description = 'Property Portfolio'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char()
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    manager_id = fields.Many2one('res.users', 'Portfolio Manager', tracking=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    property_ids = fields.One2many('re.property', 'portfolio_id')
    property_count = fields.Integer(compute='_compute_counts')
    unit_count = fields.Integer(compute='_compute_counts')
    total_valuation = fields.Monetary(compute='_compute_counts', currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.depends('property_ids', 'property_ids.unit_ids', 'property_ids.current_valuation')
    def _compute_counts(self):
        for rec in self:
            rec.property_count = len(rec.property_ids)
            rec.unit_count = sum(len(p.unit_ids) for p in rec.property_ids)
            rec.total_valuation = sum(rec.property_ids.mapped('current_valuation'))

    def action_view_properties(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('real_estate_lifecycle.action_re_property')
        action['domain'] = [('portfolio_id', '=', self.id)]
        action['context'] = {'default_portfolio_id': self.id}
        return action
