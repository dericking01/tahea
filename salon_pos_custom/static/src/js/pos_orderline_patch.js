/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";


patch(PosOrderline.prototype, {


    setEmployee(employee) {

        this.employee_id = employee.id;

        this.employee_name = employee.name;

        this.setDirty();


        console.log(
            "LINE EMPLOYEE:",
            this.employee_name
        );

    },


    getDisplayData() {

        const data = super.getDisplayData(...arguments);


        if (this.employee_name) {

            data.customerNote =
                "👤 " + this.employee_name;

        }


        return data;

    },


    serialize(options = {}) {

        const data = super.serialize(options);


        data.employee_id = this.employee_id || false;


        return data;

    },


});