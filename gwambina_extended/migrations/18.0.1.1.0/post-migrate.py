from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['stock.warehouse'].with_context(active_test=False).search([])._gw_create_receipt_confirm_type()
