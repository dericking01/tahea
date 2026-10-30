{
    'name': 'Gwambina Extended',
    'version': '18.0.1.1.0',
    'summary': 'Accounting sequence, purchase bill, GRN and inventory transfer controls for Gwambina',
    'description': """
Gwambina Extended
=================
* Journal entries re-dated to another period pick the next free sequence number of that period.
* Deliveries / internal transfers list every product whose quantity exceeds the stock on hand.
* Vendor bill lines coming from a purchase order cannot exceed their original quantity; UoM is read-only.
* Receipts (GRN) cannot receive more than the quantity ordered on the purchase order.
* Only administrators can delete lines on receipts.
* Internal transfers are confirmed by the person in charge of the destination location
  (goods wait in transit), with backorders and return-to-source for undelivered goods.
* Users can be restricted to see only their allowed stock locations.
    """,
    'author': 'Gwambina',
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'depends': ['account', 'purchase_stock', 'stock_account'],
    'data': [
        'views/account_move_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_location_views.xml',
        'views/res_users_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
