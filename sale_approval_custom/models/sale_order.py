from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
        tracking=True,
    )

    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        copy=False,
        tracking=True,
    )

    reject_reason = fields.Text(
        string="Reason for Rejection",
        readonly=True,
        copy=False,
        tracking=True,
    )

    approval_enabled = fields.Boolean(
        string='Approval Enabled',
        compute='_compute_approval_enabled',
    )

    @api.depends(
        'company_id',
        'company_id.sale_approval_required',
    )
    def _compute_approval_enabled(self):
        for order in self:
            order.approval_enabled = bool(
                order.company_id.sale_approval_required
            )

    approval_stage = fields.Selection(
        selection=[
            ('none', 'None'),
            ('waiting', 'Wait for Approval'),
            ('approved', 'Approved'),
        ],
        string='Approval Stage',
        default='none',
        copy=False,
        tracking=True,
    )

    can_approve = fields.Boolean(
        string='Can Approve',
        compute='_compute_can_approve',
    )

    @api.depends(
        'state',
        'approval_stage',
        'company_id',
        'company_id.sale_approval_required',
        'company_id.sale_approval_user_ids',
    )
    def _compute_can_approve(self):
        current_user = self.env.user
        for order in self:
            order.can_approve = bool(
                order.state == 'waiting_approval'
                and order.approval_stage == 'waiting'
                and order.company_id.sale_approval_required
                and current_user in order.company_id.sale_approval_user_ids
            )

    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Wait for Approval'),
        ],
        ondelete={
            'waiting_approval': 'set default',
        },
    )

    approval_statusbar = fields.Selection(
        selection=[
            ('draft', 'Quotation'),
            ('waiting_approval', 'Wait for Approval'),
            ('approved', 'Approved'),
            ('sent', 'Quotation Sent'),
            ('sale', 'Sales Order'),
            ('cancel', 'Cancelled'),
        ],
        string='Approval Workflow',
        compute='_compute_approval_statusbar',
        readonly=True,
    )

    @api.depends(
        'state',
        'approval_stage',
        'approval_enabled',
    )
    def _compute_approval_statusbar(self):
        for order in self:
            if not order.approval_enabled:
                order.approval_statusbar = order.state
                continue

            if order.state in ['sale', 'cancel']:
                order.approval_statusbar = order.state
                continue

            if order.state == 'sent':
                order.approval_statusbar = 'sent'
                continue

            if order.approval_stage == 'approved':
                order.approval_statusbar = 'approved'
                continue

            if order.state == 'waiting_approval':
                order.approval_statusbar = 'waiting_approval'
                continue

            order.approval_statusbar = order.state

    def action_submit_for_approval(self):
        for order in self:
            if not order.company_id.sale_approval_required:
                raise UserError(
                    "Sales Approval is not enabled for company '%s'."
                    % order.company_id.display_name
                )

            if not order.company_id.sale_approval_user_ids:
                raise UserError(
                    "Sales Approval is enabled for company '%s', "
                    "but no Sales Approvers have been assigned."
                    % order.company_id.display_name
                )

            if order.state != 'draft':
                raise UserError(
                    "Only a quotation can be submitted for approval."
                )

            order.write({
                'state': 'waiting_approval',
                'approval_stage': 'waiting',
                'approved_by': False,
                'approved_date': False,
                'reject_reason': False,
            })
        return True

    def action_approve(self):
        for order in self:
            if order.state != 'waiting_approval':
                raise UserError(
                    "This quotation is not waiting for approval."
                )

            if order.approval_stage != 'waiting':
                raise UserError(
                    "This quotation has already been processed."
                )

            if not order.company_id.sale_approval_required:
                raise UserError(
                    "Sales Approval is not enabled for this company."
                )

            approvers = order.company_id.sale_approval_user_ids

            if not approvers:
                raise UserError(
                    "No Sales Approvers have been assigned for company '%s'."
                    % order.company_id.display_name
                )

            if self.env.user not in approvers:
                raise UserError(
                    "You are not authorized to approve this quotation.\n\n"
                    "Only assigned Sales Approvers can approve "
                    "this quotation."
                )

            order.write({
                'approval_stage': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })

            order._compute_approval_statusbar()
            order.modified(['approval_stage', 'approval_statusbar'])

        return True

    def action_reject(self):
        """ Inafungua Wizard ya kuuliza sababu ya kukataa kabla ya kusitisha oda """
        self.ensure_one()
        
        if self.state != 'waiting_approval':
            raise UserError(
                "This quotation is not waiting for approval."
            )

        if self.approval_stage != 'waiting':
            raise UserError(
                "This quotation has already been processed."
            )

        if not self.company_id.sale_approval_required:
            raise UserError(
                "Sales Approval is not enabled for this company."
            )

        approvers = self.company_id.sale_approval_user_ids

        if not approvers:
            raise UserError(
                "No Sales Approvers have been assigned for company '%s'."
                % self.company_id.display_name
            )

        if self.env.user not in approvers:
            raise UserError(
                "You are not authorized to reject this quotation.\n\n"
                "Only assigned Sales Approvers can reject "
                "this quotation."
            )

        return {
            'name': 'Reason for Rejection',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id}
        }

    def action_confirm(self):
        for order in self:
            if order.company_id.sale_approval_required:
                if order.approval_stage != 'approved':
                    raise UserError(
                        "This quotation must be approved before "
                        "it can be confirmed."
                    )

                if order.state == 'waiting_approval':
                    order.write({'state': 'sent'})

        return super().action_confirm()

    def action_quotation_send(self):
        for order in self:
            if order.company_id.sale_approval_required:
                if order.approval_stage != 'approved':
                    raise UserError(
                        "This quotation must be approved before "
                        "it can be sent."
                    )

        result = super().action_quotation_send()

        for order in self:
            if (
                order.company_id.sale_approval_required
                and order.approval_stage == 'approved'
            ):
                order.write({
                    'state': 'sent',
                })

        return result


class SaleOrderRejectWizard(models.TransientModel):
    _name = 'sale.order.reject.wizard'
    _description = 'Sale Order Reject Reason Wizard'

    order_id = fields.Many2one('sale.order', string="Sales Order", required=True)
    reject_reason = fields.Text(string="Reason for Rejection", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        self.order_id.write({
            'reject_reason': self.reject_reason,
            'state': 'cancel',
            'approval_stage': 'none',
        })
        self.order_id.modified(['state', 'approval_stage', 'approval_statusbar', 'reject_reason'])
        return {'type': 'ir.actions.act_window_close'}