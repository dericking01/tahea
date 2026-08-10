/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";


patch(OrderWidget.prototype, {

    async selectEmployee() {

        const pos = this.env.services.pos;
        const dialog = this.env.services.dialog;


        const order = pos.get_order();

        const line = order?.get_selected_orderline();


        if (!line) {
            return;
        }


        console.log("POS MODELS:", pos.models);

        const employees = pos.models["hr.employee"]?.getAll() || [];

        console.log("EMPLOYEES:", employees);      


        const list = employees.map((employee) => ({

            id: employee.id,

            label: employee.name,

            item: employee,

        }));


        dialog.add(
            SelectionPopup,
            {

                title: "Select Employee",

                list: list,


                getPayload: (employee) => {


                    const selectedLine = pos
                        .get_order()
                        ?.get_selected_orderline();


                    if (!selectedLine) {
                        return;
                    }


                    selectedLine.setEmployee(
                        employee
                    );


                    console.log(
                        "Employee assigned:",
                        employee.name
                    );

                },

            }
        );

    },

});