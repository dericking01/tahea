# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

{
    "name": "Cancel Point Of Sale Orders",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Point Of Sale",
    "license": "OPL-1",
    "summary": "Cancel POS Orders, Cancel Point Of Sale Order, Cancel POS,POS Order Cancel, POS Orders Cancel, Cancel Orders, Delete POS Order ,POS Cancel, Cancel Point Of Sales,Delete POS Orders,Delete Point Of Sale Order,Delete POS Odoo pos cancel from frontend pos order cancel pos order cancel point of sale order pos order cancel from screen Cancel POS Delete POS Order POS frontend Cancel delete Point Of Sale remove pos order remove point of sale Odoo pos cancel frontend point of sale cancel frontend cancel pos frontend cancel point of sale frontend pos cancel order point of sale cancel order Cancel POS Orders, Cancel Point Of Sale Order, Cancel POS,POS Order Cancel, POS Orders Cancel, Cancel Orders, Delete POS Order ,POS Cancel, Cancel Point Of Sales,Delete POS Orders,Delete Point Of Sale Order,Delete POS Odoo pos cancel from frontend pos order cancel pos order cancel point of sale order pos order cancel from screen Cancel POS Delete POS Order POS frontend Cancel delete Point Of Sale remove pos order remove point of sale Odoo pos cancel frontend point of sale cancel frontend cancel pos frontend cancel point of sale frontend pos cancel order point of sale cancel order Mass cancel pos orders bulk cancel multiple cancel Odoo",
    "description": """This module helps to cancel point of sale orders. You can also cancel multiple orders from the tree view. You can cancel the pos orders in 2 ways,

1) Cancel and Reset to Draft: When you cancel the orders, first orders are canceled and then reset to the draft state.
2) Cancel and Delete: When you cancel the orders then first the orders are canceled and then the orders will be deleted.

We provide 2 options in the cancel POS orders,

1) Cancel Delivery Order: When you want to cancel POS orders and delivery orders then you can choose this option.
2) Cancel Invoice: When you want to cancel POS orders and invoice then you can choose this option.

If you want to cancel POS orders, delivery orders & invoice then you can choose both options "Cancel Delivery Order" & "Cancel Invoice".""",
    "version": "18.0.3.0.1",
    "depends": [
                "point_of_sale",

    ],
    "application": True,
    "data": [
        'security/pos_security.xml',
        'data/server_action_data.xml',
        'views/pos_config_settings_views.xml',
        'views/pos_order_views.xml',
    ],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price":30,
    "currency": "EUR"
}
