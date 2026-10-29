from . import models


def post_init_hook(env):
    # Existing PO bill lines: their current quantity becomes the reference ("old value").
    env.cr.execute("""
        UPDATE account_move_line
           SET po_original_qty = quantity
         WHERE purchase_line_id IS NOT NULL
    """)
    # Enable receipt confirmation on the standard internal transfer type of every warehouse.
    warehouses = env['stock.warehouse'].with_context(active_test=False).search([])
    warehouses.int_type_id.write({'gw_receipt_confirmation': True})
