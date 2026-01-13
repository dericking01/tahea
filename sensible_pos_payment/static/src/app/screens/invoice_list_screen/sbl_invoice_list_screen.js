import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";

export class InvoiceListScreen extends Component {
    static template = "sensible_pos_payment.InvoiceListScreen";
    static components = { Dialog, Input };
    static props = {
        getPayload: { type: Function },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.ui = useState(useService("ui"));
        this.state = useState({
            invoices: [],
            loading: true,
            searchQuery: "",
        });
        this.loadInvoices();
    }

    async loadInvoices() {
        try {
            this.state.loading = true;
            const invoices = await this.orm.searchRead(
                "account.move",
                [
                    ["move_type", "=", "out_invoice"],
                    ["state", "in", ["posted"]],
                    ["payment_state", "in", ["not_paid", "partial"]],
                ],
                [
                    "id",
                    "name",
                    "partner_id",
                    "amount_total",
                    "amount_residual",
                    "currency_id",
                    "invoice_date",
                    "invoice_date_due",
                ]
            );
            this.state.invoices = invoices;
        } catch (error) {
            console.error("Error loading invoices:", error);
        } finally {
            this.state.loading = false;
        }
    }

    get filteredInvoices() {
        if (!this.state.searchQuery) {
            return this.state.invoices;
        }
        const query = this.state.searchQuery.toLowerCase();
        return this.state.invoices.filter(invoice => 
            invoice.name.toLowerCase().includes(query) ||
            invoice.partner_id[1].toLowerCase().includes(query)
        );
    }

    onSelectInvoice(invoice) {
        this.props.getPayload(invoice);
        this.props.close();
    }
}