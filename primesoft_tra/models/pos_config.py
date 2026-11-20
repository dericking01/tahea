from odoo import models, fields, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    tra_receipt_enabled = fields.Boolean(
        string='Enable TRA Receipts',
        default=True,
        help='When enabled, sales of this Point of Sale can be sent to TRA as fiscal receipts. '
             'If disabled, only the standard receipt is available.',
    )
    tra_receipt_default = fields.Selection(
        selection=[('tra', 'TRA Fiscal Receipt'), ('default', 'Standard Receipt')],
        string='Default Receipt Type',
        default='tra',
        help='Which receipt type is pre-selected when the payment screen opens.',
    )
    tra_allow_standard = fields.Boolean(
        string='Allow Standard Receipt',
        default=True,
        help='When disabled, every sale is fiscalised: cashiers cannot switch to the standard receipt.',
    )
    tra_receipt_active = fields.Boolean(
        string='TRA Receipts Active',
        compute='_compute_tra_receipt_active',
        help='TRA receipts are enabled here and Point of Sale is switched on in the TRA EFD settings.',
    )

    def _compute_tra_receipt_active(self):
        use_on_pos = self.env['tra.efd.config'].sudo().search(
            [('active', '=', True)], limit=1).use_on_pos
        for config in self:
            config.tra_receipt_active = use_on_pos and config.tra_receipt_enabled

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        # An empty list means "all fields"; only extend an explicit list.
        if fields_list:
            fields_list += ['tra_receipt_active', 'tra_receipt_default', 'tra_allow_standard']
        return fields_list
