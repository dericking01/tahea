/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

export class RePortfolioDashboard extends Component {
    static template = "real_estate_lifecycle.PortfolioDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const today = new Date();
        this.state = useState({
            loading: true,
            data: null,
            showDefinitions: false,
            filters: {
                date_from: `${today.getFullYear()}-01-01`,
                date_to: today.toISOString().slice(0, 10),
                portfolio_id: "",
                property_id: "",
                building_id: "",
                property_type_id: "",
                region: "",
                manager_id: "",
                company_id: "",
            },
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const filters = {};
        for (const [k, v] of Object.entries(this.state.filters)) {
            if (v !== "" && v !== null) {
                filters[k] = v;
            }
        }
        this.state.data = await this.orm.call("re.analytics", "get_dashboard_data", [filters]);
        this.state.loading = false;
    }

    onFilter(ev) {
        this.state.filters[ev.target.name] = ev.target.value;
        if (ev.target.name === "property_id") {
            this.state.filters.building_id = "";
        }
        this.load();
    }

    get buildings() {
        const meta = this.state.data?.filters_meta;
        if (!meta) {
            return [];
        }
        const pid = parseInt(this.state.filters.property_id);
        return pid ? meta.buildings.filter((b) => b.property_id === pid) : meta.buildings;
    }

    money(value) {
        const cur = this.state.data?.currency || {};
        const txt = formatFloat(value || 0, { digits: [false, 0] });
        return cur.position === "before" ? `${cur.symbol} ${txt}` : `${txt} ${cur.symbol || ""}`;
    }

    pct(value) {
        return `${formatFloat(value || 0, { digits: [false, 1] })} %`;
    }

    num(value, digits = 0) {
        return formatFloat(value || 0, { digits: [false, digits] });
    }

    def(key) {
        return this.state.data?.definitions?.[key] || "";
    }

    get propertyIds() {
        return this.state.data?.property_ids || [];
    }

    open(model, domain, name, views = [[false, "list"], [false, "form"]], context = {}) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            views,
            context,
        });
    }

    openRecord(model, id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]] });
    }

    openProperties() {
        this.open("re.property", [["id", "in", this.propertyIds]], "Properties", [[false, "kanban"], [false, "list"], [false, "form"]]);
    }
    openUnits(extra = []) {
        const dom = [["property_id", "in", this.propertyIds], ["is_lettable", "=", true], ...extra];
        if (this.state.filters.building_id) {
            dom.push(["building_id", "=", parseInt(this.state.filters.building_id)]);
        }
        this.open("re.unit", dom, "Units");
    }
    openVacant() {
        this.openUnits([["occupancy_status", "=", "vacant"]]);
    }
    openOccupied() {
        this.openUnits([["occupancy_status", "=", "occupied"]]);
    }
    openAgeing() {
        this.action.doAction("real_estate_lifecycle.action_re_ageing");
    }
    openInvoices() {
        const f = this.state.filters;
        this.open("account.move", [["re_property_id", "in", this.propertyIds], ["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"], ["invoice_date", ">=", f.date_from], ["invoice_date", "<=", f.date_to]], "Rental Invoices");
    }
    openExpiring() {
        this.action.doAction("real_estate_lifecycle.action_re_lease_expiring");
    }
    openOverdueWos() {
        this.open("re.work.order", [["property_id", "in", this.propertyIds], ["is_overdue", "=", true]], "Overdue Work Orders");
    }
    openExceptions() {
        this.open("re.exception", [["property_id", "in", this.propertyIds], ["state", "in", ["new", "investigating"]]], "Open Exceptions");
    }
    openLedger() {
        const f = this.state.filters;
        this.open("account.move.line", [["re_property_id", "in", this.propertyIds], ["parent_state", "=", "posted"], ["date", ">=", f.date_from], ["date", "<=", f.date_to], ["account_id.account_type", "in", ["income", "income_other", "expense", "expense_direct_cost"]]], "Property P&L", [[false, "pivot"], [false, "list"]], { pivot_row_groupby: ["re_property_id"], pivot_column_groupby: ["account_id"] });
    }
    openServiceCharges() {
        this.action.doAction("real_estate_lifecycle.action_re_sc_budget");
    }
    openMaintenance() {
        const f = this.state.filters;
        this.open("re.work.order", [["property_id", "in", this.propertyIds], ["date_request", ">=", f.date_from], ["date_request", "<=", f.date_to]], "Work Orders", [[false, "pivot"], [false, "list"], [false, "form"]]);
    }
    async runChecks() {
        await this.orm.call("re.exception", "run_checks", []);
        await this.load();
    }
}

registry.category("actions").add("re_portfolio_dashboard", RePortfolioDashboard);
