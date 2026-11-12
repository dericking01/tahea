from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    picking_id = fields.Many2one(
        'stock.picking',
        string='GRN Reference',
        readonly=True,
        copy=False,
        help="Reference to the Goods Receipt Note (GRN) from which this bill was created"
    )

    def action_open_picking_stat(self):
        """Open linked Picking (stat button) from Vendor Bill."""
        self.ensure_one()

        if not self.picking_id:
            raise UserError(
                _("No GRN (Goods Receipt Note) is linked to this Vendor Bill.")
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _("GRN: %s") % self.picking_id.name,
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('stock.view_picking_form').id, 'form')],
            'target': 'current',
        }

