# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    re_work_order_id = fields.Many2one('re.work.order', 'Work Order', index=True, copy=False, tracking=True)
    re_property_id = fields.Many2one('re.property', 'Property', compute='_compute_re_property', store=True,
                                     readonly=False, index=True)
    re_is_selected = fields.Boolean(compute='_compute_re_is_selected')

    @api.depends('re_work_order_id')
    def _compute_re_property(self):
        for po in self:
            po.re_property_id = po.re_work_order_id.property_id or po.re_property_id

    def _compute_re_is_selected(self):
        for po in self:
            po.re_is_selected = bool(po.re_work_order_id and po.re_work_order_id.selected_po_id == po)

    def action_re_select_for_work_order(self):
        self.ensure_one()
        if not self.re_work_order_id:
            raise UserError(_('This quotation is not linked to a work order.'))
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Only quotations (RFQs) can be selected.'))
        if not self.amount_untaxed:
            raise UserError(_('Enter the vendor quoted prices first.'))
        self.re_work_order_id._re_select_quotation(self)
        return {'type': 'ir.actions.act_window', 'res_model': 're.work.order', 'res_id': self.re_work_order_id.id,
                'view_mode': 'form'}

    def button_confirm(self):
        """Purchase orders for real-estate work orders require an approved work-order
        budget that covers the order amount (vendor-selection control)."""
        fm = self.env.user.has_group('real_estate_lifecycle.group_re_finance_manager')
        for po in self.filtered('re_work_order_id'):
            wo = po.re_work_order_id
            amount = po.currency_id._convert(po.amount_untaxed, wo.currency_id, wo.company_id,
                                             fields.Date.context_today(self))
            tol = wo.company_id.re_bill_tolerance_pct / 100.0
            problems = []
            if not wo._re_is_approved() and not wo.is_emergency:
                problems.append(_('work order %s is not approved', wo.name))
            elif amount > wo.approved_budget * (1 + tol) + 0.005:
                problems.append(_('order amount %(a)s exceeds the approved budget %(b)s',
                                  a=wo.currency_id.format(amount), b=wo.currency_id.format(wo.approved_budget)))
            if problems:
                if not fm and not self.env.su:
                    raise UserError(_('Cannot confirm %(po)s: %(p)s.', po=po.name, p='; '.join(problems)))
                self.env['re.exception']._re_raise('control_override', po, po.company_id,
                                                   _('PO %(po)s confirmed by %(u)s despite: %(p)s', po=po.name,
                                                     u=self.env.user.name, p='; '.join(problems)),
                                                   prop=wo.property_id, amount=amount - wo.approved_budget)
        return super().button_confirm()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move)
        if not res.get('analytic_distribution') and self.order_id.re_property_id:
            wo = self.order_id.re_work_order_id
            res['analytic_distribution'] = self.order_id.re_property_id._re_analytic_distribution(wo.building_id)
        return res
