import { _t } from "@web/core/l10n/translation";
import { useErrorHandlers, useTrackedAsync } from "@point_of_sale/app/utils/hooks";
import { registry } from "@web/core/registry";
import { PaymentReceipt } from "@sensible_pos_payment/app/screens/receipt_screen/receipt/sbl_payment_receipt";
import { useState, Component, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PaymentReceiptScreen extends Component {
    static template = "sensible_pos_payment.PaymentReceiptScreen";
    static components = { PaymentReceipt };
    static props = {
        payment: Object,
        companyData: { type: Object, optional: true },
    };

    setup() {
        super.setup();
        this.pos = usePos();
        useErrorHandlers();
        this.ui = useState(useService("ui"));
        this.renderer = useService("renderer");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        
        // Get partner from payment instead of order
        const partner = this.props.payment.partner_id ? {
            email: "", // Will be loaded from partner data
            mobile: "", // Will be loaded from partner data
        } : {};
        
        this.state = useState({
            email: partner?.email || "",
            phone: partner?.mobile || "",
            companyData: this.props.companyData || null,
        });
        
        this.sendReceipt = useTrackedAsync(this._sendReceiptToCustomer.bind(this));
        this.doFullPrint = useTrackedAsync(() => this.printPaymentReceipt(this.props.payment));
        
        // Load company and partner data if not provided
        if (!this.props.companyData) {
            this._loadCompanyData();
        }
    }

    async _loadCompanyData() {
        try {
            // Get company data from payment
            const companyId = this.props.payment.company_id ? this.props.payment.company_id[0] : this.pos.company.id;
            const companyData = await this.pos.data.searchRead("res.company", [["id", "=", companyId]], [
                "name", "email", "phone", "website", "logo"
            ]);
            
            // Get partner data if available
            let partnerData = null;
            if (this.props.payment.partner_id) {
                partnerData = await this.pos.data.searchRead("res.partner", [["id", "=", this.props.payment.partner_id[0]]], [
                    "email", "mobile"
                ]);
            }
            
            this.state.companyData = {
                company: companyData.length ? {
                    id: companyId,
                    name: companyData[0].name,
                    email: companyData[0].email,
                    phone: companyData[0].phone,
                    website: companyData[0].website,
                } : this.pos.company,
                header: "", // Can be configured if needed
                cashier: this.pos.get_cashier().name,
            };
            
            // Update partner contact info
            if (partnerData && partnerData.length) {
                this.state.email = partnerData[0].email || "";
                this.state.phone = partnerData[0].mobile || "";
            }
            
        } catch (error) {
            console.error("Error loading company data:", error);
            // Fallback to pos company data
            this.state.companyData = {
                company: this.pos.company,
                header: "",
                cashier: this.pos.get_cashier().name,
            };
        }
    }

    _addNewOrder() {
        this.pos.add_new_order();
    }
    
    continueToProductScreen() {
        this.pos.showScreen("ProductScreen");
    }
    actionSendReceiptOnEmail() {
        this.sendReceipt.call({
            action: "sbl_action_send_receipt",
            destination: this.state.email,
            name: "Email",
        });
    }
    get headerData() {
        return this.state.companyData;
    }
    get nextScreen() {
        return { name: "ProductScreen" };
    }
    get ticketScreen() {
        return { name: "TicketScreen" };
    }
    get isValidEmail() {
        return this.state.email && /^.+@.+$/.test(this.state.email);
    }
    get isValidPhone() {
        return this.state.phone && /^\+?[()\d\s-.]{8,18}$/.test(this.state.phone);
    }
    showPhoneInput() {
        return false;
    }
    generateTicketImage = async () => {
        if (!this.state.companyData) {
            await this._loadCompanyData();
        }
        
        if (!this.state.companyData) {
            throw new Error("Cannot generate receipt image without company data");
        }
        
        return await this.renderer.toJpeg(
            PaymentReceipt,
            {
                data: this.state.companyData,
                formatCurrency: this.env.utils.formatCurrency,
                payment: this.props.payment,
            },
            { addClass: "sbl_pos_receipt_print p-3" }
        );
    }
    async _sendReceiptToCustomer({ action, destination }) {
        const fullTicketImage = await this.generateTicketImage();
        await this.pos.data.call("account.payment", action, [
            [this.props.payment.id],
            destination,
            fullTicketImage,
        ]);
    }
    async printPaymentReceipt() {
        // Ensure company data is loaded before printing
        if (!this.state.companyData) {
            await this._loadCompanyData();
        }
        
        // Verify we have the required data
        if (!this.state.companyData) {
            this.notification.add("Unable to load company data for receipt", { type: "danger" });
            return false;
        }
        
        await this.pos.printer.print(
            PaymentReceipt,
            {
                data: this.state.companyData,
                formatCurrency: this.env.utils.formatCurrency,
                payment: this.props.payment,
            },
            { webPrintFallback: true }
        );
        return true;
    }
}

registry.category("pos_screens").add("PaymentReceiptScreen", PaymentReceiptScreen);
