{
    "name": "Salon POS Custom",
    "version": "18.0.1.0.0",
    "sequence": -12,
    "category": "Point of Sale",
    "summary": "Custom POS features for Salon",

    "depends": [
        "point_of_sale",
        "hr",
    ],

    "data": [
        # ======================================================
        # SECURITY
        # ======================================================

        "security/ir.model.access.csv",

        # ======================================================
        # VIEWS
        # ======================================================

        "views/pos_order_line_views.xml",
        "views/pos_order_views.xml",

        # ======================================================
        # COMMISSION WIZARD
        # Existing PDF + Excel report
        # ======================================================

        "views/commission_report_wizard_views.xml",

        # ======================================================
        # EXISTING COMMISSION REPORT
        # DO NOT REMOVE
        # ======================================================

        "report/employee_commission_report.xml",
        "report/employee_commission_template.xml",

        # ======================================================
        # NEW SELECTED/ALL COMMISSION PRINT REPORT
        # ======================================================

        "report/employee_commission_selected_report.xml",
        "report/employee_commission_selected_template.xml",
    ],

    # ==========================================================
    # POS JAVASCRIPT / XML ASSETS
    # ==========================================================

    "assets": {
        "point_of_sale._assets_pos": [
            "salon_pos_custom/static/src/js/employee_button.js",
            "salon_pos_custom/static/src/js/pos_orderline_patch.js",

            "salon_pos_custom/static/src/xml/employee_button.xml",
            "salon_pos_custom/static/src/xml/orderline.xml",
        ],
    },

    # ==========================================================
    # MODULE SETTINGS
    # ==========================================================

    "installable": True,
    "application": True,
    "license": "LGPL-3",
}