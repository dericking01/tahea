from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Receipt confirmations now ask Create Backorder / No Backorder - Return to Source
    env = api.Environment(cr, SUPERUSER_ID, {})
    types = env['stock.warehouse'].with_context(active_test=False).search([]).gw_receipt_confirm_type_id
    types.filtered(lambda t: t.create_backorder == 'always').write({'create_backorder': 'ask'})
