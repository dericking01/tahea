from odoo import api, models


class EmployeeCommissionReport(models.AbstractModel):

    _name = "report.salon_pos_custom.employee_commission_template"
    _description = "Employee Commission Report"

    @api.model
    def _get_report_values(self, docids, data=None):

        # ==========================================================
        # WIZARD
        # ==========================================================

        wizard = self.env[
            "commission.report.wizard"
        ].browse(docids)

        employees = {}

        date_from = False
        date_to = False
        selected_employee = False
        employee_selection = "all"

        # ==========================================================
        # GET DATA FROM WIZARD
        # ==========================================================

        if data:

            employee_selection = data.get(
                "employee_selection",
                "all",
            )

            employee_id = data.get(
                "employee_id"
            )

            date_from = data.get(
                "date_from"
            )

            date_to = data.get(
                "date_to"
            )

            # ======================================================
            # SELECTED EMPLOYEE NAME
            # ======================================================

            if (
                employee_selection == "employee"
                and employee_id
            ):

                employee = self.env[
                    "hr.employee"
                ].browse(employee_id)

                if employee.exists():

                    selected_employee = employee.name

            elif employee_selection == "all":

                selected_employee = "All Employees"

            # ======================================================
            # SEARCH DOMAIN
            # ======================================================

            domain = []

            # Specific employee only
            if (
                employee_selection == "employee"
                and employee_id
            ):

                domain.append(
                    (
                        "employee_id",
                        "=",
                        employee_id,
                    )
                )

            # From date
            if date_from:

                domain.append(
                    (
                        "order_id.date_order",
                        ">=",
                        date_from,
                    )
                )

            # To date
            if date_to:

                domain.append(
                    (
                        "order_id.date_order",
                        "<=",
                        date_to,
                    )
                )

            # ======================================================
            # GET POS ORDER LINES
            # ======================================================

            lines = self.env[
                "pos.order.line"
            ].search(
                domain,
                order="employee_id, id",
            )

            # ======================================================
            # GROUP LINES BY EMPLOYEE
            # ======================================================

            for line in lines:

                employee = line.employee_id

                # Skip lines without employee
                if not employee:
                    continue

                # Create employee group
                if employee.id not in employees:

                    employees[
                        employee.id
                    ] = {

                        "name":
                            employee.name,

                        "lines":
                            [],

                        "total_price":
                            0.0,

                        "total_commission":
                            0.0,

                    }

                # ==================================================
                # ADD LINE
                # ==================================================

                employees[
                    employee.id
                ]["lines"].append(line)

                # ==================================================
                # TOTAL PRICE
                # ==================================================

                line_total_price = (
                    line.qty *
                    line.price_unit
                )

                employees[
                    employee.id
                ]["total_price"] += (
                    line_total_price
                )

                # ==================================================
                # TOTAL COMMISSION
                # ==================================================

                employees[
                    employee.id
                ]["total_commission"] += (
                    line.commission_amount
                    or 0.0
                )

        # ==========================================================
        # GRAND TOTAL PRICE
        # ==========================================================

        grand_total_price = sum(
            emp["total_price"]
            for emp in employees.values()
        )

        # ==========================================================
        # GRAND TOTAL COMMISSION
        # ==========================================================

        grand_total_commission = sum(
            emp["total_commission"]
            for emp in employees.values()
        )

        # ==========================================================
        # RETURN REPORT DATA
        # ==========================================================

        return {

            "doc_ids":
                docids,

            "doc_model":
                "commission.report.wizard",

            "docs":
                wizard,

            "employees":
                employees,

            "date_from":
                date_from,

            "date_to":
                date_to,

            "selected_employee":
                selected_employee,

            "employee_selection":
                employee_selection,

            "grand_total_price":
                grand_total_price,

            "grand_total_commission":
                grand_total_commission,

        }