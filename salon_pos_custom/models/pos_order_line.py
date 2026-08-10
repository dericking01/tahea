from odoo import models, fields, api


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    # ==========================================================
    # EMPLOYEE
    # ==========================================================

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        index=True,
    )

    # ==========================================================
    # COMMISSION
    # ==========================================================

    commission_amount = fields.Monetary(
        string="Commission",
        currency_field="currency_id",
        compute="_compute_commission_amount",
        store=True,
        index=True,
    )

    # ==========================================================
    # ORDER DATE
    # Related from POS Order
    # ==========================================================

    commission_date = fields.Datetime(
        string="Order Date",
        related="order_id.date_order",
        store=True,
        index=True,
    )

    # ==========================================================
    # ORDER
    # ==========================================================

    commission_order_id = fields.Many2one(
        "pos.order",
        string="Order",
        related="order_id",
        store=True,
        index=True,
    )

    # ==========================================================
    # COMMISSION COMPUTATION
    # ==========================================================

    @api.depends(
        "price_unit",
        "qty",
        "employee_id",
    )
    def _compute_commission_amount(self):

        for line in self:

            # --------------------------------------------------
            # NO EMPLOYEE = NO COMMISSION
            # --------------------------------------------------

            if not line.employee_id:
                line.commission_amount = 0.0
                continue

            service_price = line.price_unit
            qty = line.qty or 0.0

            commission_per_service = 0.0

            # --------------------------------------------------
            # RULE 1
            #
            # 5,000 - 20,000
            # Commission = 30% of selling price
            # --------------------------------------------------

            if 5000 <= service_price <= 20000:

                commission_per_service = (
                    service_price * 0.30
                )

            # --------------------------------------------------
            # RULE 2
            #
            # 25,000 - 45,000
            # Commission = 30% of 20,000
            # --------------------------------------------------

            elif 25000 <= service_price <= 45000:

                commission_per_service = (
                    20000 * 0.30
                )

            # --------------------------------------------------
            # RULE 3
            #
            # 50,000+
            # Commission = 30% of 40,000
            # --------------------------------------------------

            elif service_price >= 50000:

                commission_per_service = (
                    40000 * 0.30
                )

            # --------------------------------------------------
            # FINAL COMMISSION
            # --------------------------------------------------

            line.commission_amount = (
                commission_per_service * qty
            )

    # ==========================================================
    # RECEIVE EMPLOYEE FROM POS
    # ==========================================================

    def _order_line_fields(
        self,
        line,
        session_id=None,
    ):

        vals = super()._order_line_fields(
            line,
            session_id,
        )

        if line.get("employee_id"):

            vals[2]["employee_id"] = (
                line["employee_id"]
            )

        return vals