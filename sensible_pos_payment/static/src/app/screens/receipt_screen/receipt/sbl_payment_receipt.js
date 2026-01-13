import { Component } from "@odoo/owl";
import { PaymentReceiptHeader } from "@sensible_pos_payment/app/screens/receipt_screen/receipt/receipt_header/sbl_payment_receipt_header";
import { omit } from "@web/core/utils/objects";

export class PaymentReceipt extends Component {
    static template = "sensible_pos_payment.PaymentReceipt";
    static components = {
        PaymentReceiptHeader,
    };
    static props = {
        data: { type: Object, optional: true },
        formatCurrency: Function,
        payment: Object,
    };
    omit(...args) {
        return omit(...args);
    }
}
