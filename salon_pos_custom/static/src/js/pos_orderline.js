/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";


patch(PosOrderline.prototype, {

    setup() {
        super.setup(...arguments);

        this.employee_id = false;
    },


    setEmployee(employee_id) {

        this.employee_id = employee_id;

    },


    getEmployee() {

        return this.employee_id;

    },


    export_as_JSON() {

        const json = super.export_as_JSON(...arguments);

        json.employee_id = this.employee_id || false;

        return json;

    },


});