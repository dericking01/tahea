/** @odoo-module **/

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";

// Seller details come from the TRA EFD settings (Test Connection) or the Odoo company.
const HEADER_KEYS = [
    "company_name",
    "company_address",
    "company_mobile",
    "company_tin",
    "company_vrn",
    "company_serial",
    "company_uin",
    "tax_office",
];

patch(OrderReceipt.prototype, {
    setup() {
        super.setup(...arguments);

        this.orm = useService("orm");

        const d = this.props.data || {};
        const header = Object.fromEntries(HEADER_KEYS.map((key) => [key, ""]));
        // Shown until the server answers, and when the POS is offline
        header.company_name = d.headerData?.company?.name || "";

        this.traState = useState({
            receipt_type:          d.tra_receipt_type || "default",
            tra_submitted:         false,
            tra_is_demo:           false,
            tra_receipt_number:    "",
            tra_z_number:          "",
            tra_receipt_datetime:  "",
            tra_verification_code: "",
            tra_qr_url:            "",
            tra_qr_image:          "",
            tra_error:             "",
            tra_customer_tin:      d.tra_customer_tin || "",
            ...header,
        });

        onWillStart(async () => {
            await this._fetchTraReceiptData();
        });
    },

    async _fetchTraReceiptData() {
        const orderId = this.props.data?.tra_order_id;
        try {
            // Unsynced (offline) order: only the header can be shown, TRA fields stay PENDING.
            const result = orderId
                ? await this.orm.call("pos.order", "get_tra_receipt_data", [orderId])
                : await this.orm.call("pos.order", "get_tra_receipt_header", []);
            this._applyTraData(result || {});
        } catch (err) {
            console.error("TRA EFD: could not load receipt data", err);
        }
    },

    _applyTraData(result) {
        const values = {};
        for (const [key, value] of Object.entries(result)) {
            if (key === "tra_receipt_type") {
                values.receipt_type = value || this.traState.receipt_type;
            } else if (key in this.traState) {
                values[key] = value || this.traState[key];
            }
        }
        Object.assign(this.traState, values);
    },

    get traReceiptType() {
        return this.traState.receipt_type;
    },

    get traQrSrc() {
        return this.traState.tra_qr_image;
    },

    get traCompanyLogo() {
        const companyId = this.props.data?.headerData?.company?.id;
        return companyId ? `/web/image?model=res.company&id=${companyId}&field=logo` : "";
    },
});
