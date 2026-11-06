{
    'name': 'Inter-Company Stock Transfer',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Transfer stock between warehouses of different companies '
               'through the native inter-company transit location',
    'description': """
Inter-Company Stock Transfer
============================
Lets explicitly authorized users move stock from a location of one company
to a location of another company of the same database.

Each transfer is executed as two native, company-consistent operations:

* a delivery in the source company (source location -> Inter-company transit)
* a receipt in the destination company (Inter-company transit -> destination
  location), generated from what was actually dispatched.

Partial dispatches/receipts, backorders, lots/serials, returns and stock
valuation are handled by the standard stock engine.
""",
    'author': 'AfyaCall',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'security/intercompany_stock_transfer_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/intercompany_transfer_cancel_views.xml',
        'views/intercompany_transfer_views.xml',
        'views/stock_picking_views.xml',
        'views/intercompany_transfer_menus.xml',
    ],
    'installable': True,
    'application': False,
}
