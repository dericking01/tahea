import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";

export class PaymentReceiptHeader extends Component {
    static template = "sensible_pos_payment.PaymentReceiptHeader";
    static props = {
        data: {
            type: Object,
            shape: {
                company: Object,
                header: { type: [String, { value: false }], optional: true },
                cashier: { type: String, optional: true },
                "*": true,
            },
        },
    };
}
