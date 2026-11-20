/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const onlyDigits = (value) => (value || "").replace(/\D/g, "");

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.traDialog = useService("dialog");

        const config = this.pos.config;
        const order = this.currentOrder;
        // Active = enabled on this Point of Sale and Point of Sale is on in the TRA EFD settings
        const isEnabled = !!config.tra_receipt_active;
        const allowStandard = config.tra_allow_standard !== false;
        // The API has no credit note, so a refund always prints the standard receipt
        const isRefund = order.get_total_with_tax() < 0;

        let type = order.tra_receipt_type;
        if (!isEnabled || isRefund) {
            type = "default";
        } else if (!allowStandard) {
            type = "tra";
        } else if (!type) {
            type = config.tra_receipt_default || "tra";
        }
        order.setTraReceiptType(type);

        // Pre-fill the TIN from the customer when it looks like a TIN (9 digits)
        const partner = order.get_partner();
        const partnerTin = [partner?.tra_tin, partner?.vat]
            .map(onlyDigits)
            .find((digits) => digits.length === 9);
        const tin = order.tra_customer_tin || partnerTin || "";

        this.traState = useState({
            enabled: isEnabled && !isRefund,
            allowStandard,
            activeType: type,
            customerTin: tin,
        });
    },

    get traReceiptEnabled() { return this.traState.enabled; },
    get traAllowStandard() { return this.traState.allowStandard; },
    get isTraReceiptSelected() { return this.traState.activeType === "tra"; },

    toggleTraReceiptType(type) {
        if (type === "default" && !this.traState.allowStandard) {
            return;
        }
        this.currentOrder.setTraReceiptType(type);
        this.traState.activeType = type;
    },

    async _isOrderValid(isForceValidate) {
        if (this.traState.enabled) {
            const order = this.currentOrder;
            const tin = onlyDigits(this.traState.customerTin);
            if (this.isTraReceiptSelected && tin && tin.length !== 9) {
                this.traDialog.add(AlertDialog, {
                    title: _t("Invalid Customer TIN"),
                    body: _t("A TRA TIN has exactly 9 digits. Correct it or leave the field empty."),
                });
                return false;
            }
            order.tra_customer_tin = this.isTraReceiptSelected ? tin : "";
        }
        return super._isOrderValid(...arguments);
    },
});
