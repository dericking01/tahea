from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Extend existing state field
    state = fields.Selection(
        selection_add=[
            ('submitted', 'Submitted for Approval'),
            ('ops_approved', 'PM Approved'),
            ('controller_approved', 'Supply Chain Manager Approved'),
            ('finance_approved', 'Finance Approved')
        ],
        tracking=True
    )

    # Approval tracking fields
    approved_ops_id = fields.Many2one('res.users', string="PM Approved By", readonly=True)
    approval_date_ops = fields.Datetime(string="PM Approval Date", readonly=True)
    approved_controller_id = fields.Many2one('res.users', string="Supply Chain Manager Approved By", readonly=True)
    approval_date_controller = fields.Datetime(string="Supply Chain Manager Approval Date", readonly=True)
    approved_finance_id = fields.Many2one('res.users', string="Finance Approved By", readonly=True)
    approval_date_finance = fields.Datetime(string="Finance Approval Date", readonly=True)


    def copy(self, default=None): 
        default = dict(default or {})
        # Clear approval tracking fields when duplicating
        default.update({
            'approved_ops_id': False,
            'approval_date_ops': False,
            'approved_controller_id': False,
            'approval_date_controller': False,
            'approved_finance_id': False,
            'approval_date_finance': False,
        })
        return super(PurchaseOrder, self).copy(default)

    # Sequential approval actions
    def action_submit_for_approval(self):
        for order in self:
            if order.state != 'draft':
                raise UserError(_("Only draft orders can be submitted for approval."))
            order.state = 'submitted'
            order.message_post(body=_("Purchase Order submitted for approval by %s") % self.env.user.name)

    def action_approve_ops(self):
        group_xmlid = 'purchase_sequential_approval.group_ops_manager'
        for order in self:
            if order.state != 'submitted':
                raise UserError(_('Order must be in Submitted state for Operations approval.'))
            if not self.env.user.has_group(group_xmlid):
                raise UserError(_('You are not authorized to approve as Operations Manager.'))
            order.approved_ops_id = self.env.user
            order.approval_date_ops = fields.Datetime.now()
            order.state = 'ops_approved'
            order.message_post(body=_('Approved by Operations: %s') % self.env.user.name)

    def action_approve_controller(self):
        group_xmlid = 'purchase_sequential_approval.group_chief_controller'
        for order in self:
            if order.state != 'ops_approved':
                raise UserError(_('Order must be approved by Operations first.'))
            if not self.env.user.has_group(group_xmlid):
                raise UserError(_('You are not authorized to approve as Chief Controller.'))
            order.approved_controller_id = self.env.user
            order.approval_date_controller = fields.Datetime.now()
            order.state = 'controller_approved'
            order.message_post(body=_('Approved by Controller: %s') % self.env.user.name)

    def action_approve_finance(self):
        group_xmlid = 'purchase_sequential_approval.group_finance_manager'
        for order in self:
            if order.state != 'controller_approved':
                raise UserError(_('Order must be approved by Controller first.'))
            if not self.env.user.has_group(group_xmlid):
                raise UserError(_('You are not authorized to approve as Finance Manager.'))
            order.approved_finance_id = self.env.user
            order.approval_date_finance = fields.Datetime.now()
            order.state = 'finance_approved'
            order.message_post(body=_('Approved by Finance: %s') % self.env.user.name)

    def action_reject(self, reason=None):
        allowed_groups = [
            'purchase_sequential_approval.group_ops_manager',
            'purchase_sequential_approval.group_chief_controller',
            'purchase_sequential_approval.group_finance_manager',
        ]
        for order in self:
            if not any(self.env.user.has_group(g) for g in allowed_groups):
                raise UserError(_('You are not authorized to reject this PO.'))
            order.state = 'draft'
            order.message_post(body=_('Purchase Order rejected by %s. %s') % (self.env.user.name, reason or ''))

    def button_confirm(self):
        for order in self:
            # Allow confirming if finance_approved
            if order.state == 'finance_approved':
                order.state = 'draft'  # Temporary to pass Odoo checks
                super(PurchaseOrder, order).button_confirm()
                # No need to reset state, Odoo will move to 'purchase'
            elif order.state == 'draft':
                super(PurchaseOrder, order).button_confirm()
            else:
                raise UserError(_('Order must be in draft or finance approved state to confirm.'))
        return True
