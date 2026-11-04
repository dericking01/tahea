from odoo import models, fields, api, _
from ..models.tra_receipt import IDTYPE_MAP


class TraReceiptConfirm(models.TransientModel):
    _name = 'tra.receipt.confirm'
    _description = 'Confirm TRA Receipt Details'

    move_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='Customer Record')

    # Exactly what the payload will contain
    customer_name = fields.Char(string='Customer Name', readonly=True)
    customer_id_type = fields.Char(string='ID Type', readonly=True)
    customer_id_number = fields.Char(string='TIN / ID Number', readonly=True)
    customer_mobile = fields.Char(string='Mobile', readonly=True)
    item_count = fields.Integer(string='Lines', readonly=True)
    total_excl_tax = fields.Float(string='Total Excl. Tax (TZS)', digits=(16, 2), readonly=True)
    total_tax = fields.Float(string='VAT (TZS)', digits=(16, 2), readonly=True)
    total_incl_tax = fields.Float(string='Total Incl. Tax (TZS)', digits=(16, 2), readonly=True)
    invoice_total = fields.Monetary(related='move_id.amount_total', string='Invoice Total')
    currency_id = fields.Many2one(related='move_id.currency_id')
    warning = fields.Text(readonly=True)

    @api.model
    def _open_for_move(self, move):
        """Build the payload now, so the user confirms the data that will be sent."""
        payload = move._build_tra_payload()
        customer = payload['customer']
        items = payload['items']
        has_tin = customer['idtype'] == '1'

        warnings = []
        if not has_tin:
            warnings.append(_('No valid TIN on this customer, so TRA will identify them by telephone (%s). '
                              'Cancel and add the TIN on the customer if they have one.',
                              customer['mobile'] or _('none')))
        if move.currency_id != move.company_id.currency_id:
            warnings.append(_('This invoice is in %s. TRA receives the amounts converted to TZS.',
                              move.currency_id.name))
        if move.partner_id.name != customer['name']:
            warnings.append(_('Special characters were removed from the name TRA receives.'))

        wizard = self.create({
            'move_id': move.id,
            'customer_name': customer['name'],
            'customer_id_type': IDTYPE_MAP.get(customer['idtype'], ''),
            'customer_id_number': customer['idnumber'],
            'customer_mobile': customer['mobile'],
            'item_count': len(items),
            'total_excl_tax': sum(item['net'] for item in items),
            'total_tax': sum(item['tax'] for item in items),
            'total_incl_tax': sum(item['amount'] for item in items),
            'warning': '\n'.join(warnings) or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirm TRA Receipt for %s', move.name),
            'res_model': self._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        self.ensure_one()
        return self.move_id._action_issue_tra_receipt(
            next_action={'type': 'ir.actions.act_window_close'})
