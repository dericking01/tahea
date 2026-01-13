import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { InvoiceListScreen } from "@sensible_pos_payment/app/screens/invoice_list_screen/sbl_invoice_list_screen";

patch(PosStore.prototype, {
    async selectPaymentPartner() {
        const payload = await makeAwaitable(this.dialog, PartnerList);
        if(!payload || !payload.id) {
            return;
        }
        this.action.doAction('sensible_pos_payment.sbl_pos_account_payment_register_action', {
            additionalContext: {'default_partner_id': payload.id, 'default_payment_type': 'inbound'},
            props: {
                onSave: async (record) => {
                    const paymentId = record.evalContext.id;
                    await this.data.call("account.payment", "action_post", [paymentId]);
                    
                    this.action.doAction({
                        type: "ir.actions.act_window_close",
                    });
                    
                    // Get complete payment data using Python method
                    const receiptData = await this.data.call("account.payment", "sbl_get_payment_receipt_data", [paymentId]);
                    
                    const props = {
                        payment: receiptData.payment,
                        companyData: receiptData.company_data
                    };
                    
                    this.showScreen("PaymentReceiptScreen", props);
                }
            }
        });
    },
    async selectInvoices() {
        const payload = await makeAwaitable(this.dialog, InvoiceListScreen);
        if (!payload || !payload.id) {
            return;
        }
        
        this.action.doAction('sensible_pos_payment.sbl_account_invoice_payment_register_form_action', {
            additionalContext: {
                'active_model': 'account.move',
                'active_ids': [payload.id],
            },
            props: {
                onSave: async (record) => {
                    // Call action_create_payments on the payment register to get actual payment ID
                    const paymentAction = await this.data.call("account.payment.register", "action_create_payments", [record.evalContext.id]);
                    
                    this.action.doAction({
                        type: "ir.actions.act_window_close",
                    });
                    
                    // Extract payment ID from the action result
                    let paymentId;
                    if (paymentAction && paymentAction.res_id) {
                        paymentId = paymentAction.res_id;
                    } else if (paymentAction && paymentAction.res_ids && paymentAction.res_ids.length > 0) {
                        paymentId = paymentAction.res_ids[0];
                    } else if (paymentAction && paymentAction.domain) {
                        // Parse domain to extract payment ID
                        const domainStr = JSON.stringify(paymentAction.domain);
                        const idMatch = domainStr.match(/\["id","in",\[(\d+)\]/);
                        if (idMatch) {
                            paymentId = parseInt(idMatch[1]);
                        }
                    }
                    
                    if (!paymentId) {
                        this.notification.add(_t("Could not retrieve payment ID"), { type: "danger" });
                        console.error("Payment action result:", paymentAction);
                        return;
                    }
                    
                    // Get complete payment data using Python method
                    const receiptData = await this.data.call("account.payment", "sbl_get_payment_receipt_data", [paymentId]);
                    
                    const props = {
                        payment: receiptData.payment,
                        companyData: receiptData.company_data
                    };
                    
                    this.showScreen("PaymentReceiptScreen", props);
                }
            }
        });
    },
});