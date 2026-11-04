/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TraDashboard extends Component {
    static template = "zalongwa_tra_efd.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, api: null, syncing: false, syncError: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("tra.receipt", "get_dashboard_data", []);
        this.loadApiTotals();
    }

    async loadApiTotals() {
        this.state.api = null;
        this.state.api = await this.orm.call("tra.receipt", "get_dashboard_api_totals", []);
    }

    async sync() {
        this.state.syncing = true;
        this.state.syncError = null;
        try {
            const result = await this.orm.call("tra.receipt", "action_dashboard_sync", []);
            this.state.syncError = result.error || null;
            await this.load();
        } finally {
            this.state.syncing = false;
        }
    }

    money(value) {
        return new Intl.NumberFormat(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    get monthDifference() {
        const totals = this.state.data.totals;
        return this.state.api.month_amount - totals[2].value;
    }

    get todayCount() {
        return this.state.data.totals[0].value;
    }

    openList(name, resModel, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openDay(day) {
        this.openList(day.label, "tra.receipt", [
            ["status", "=", "success"],
            ["is_demo", "=", false],
            ["receipt_date", "=", day.date],
        ]);
    }

    openReceipt(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "tra.receipt",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openZReports() {
        this.action.doAction("zalongwa_tra_efd.action_tra_zreport");
    }
}

registry.category("actions").add("zalongwa_tra_efd.dashboard", TraDashboard);
