/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);

        // TRA Receipt Type (set on the payment screen, or loaded from the server on reprint)
        result.tra_receipt_type = this.tra_receipt_type || "default";
        result.tra_customer_tin = this.tra_customer_tin || "";

        // Backend id: the record id becomes the server integer once the order is synced
        result.tra_order_id = typeof this.id === "number" ? this.id : null;

        return result;
    },

    setTraReceiptType(type) {
        this.tra_receipt_type = type;
    },
});
