/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { Component, markup } from "@odoo/owl";

const FALLBACK_HTML_MESSAGE = "<div class='alert alert-warning m-4'>Dashboard data not found in context. Please regenerate the ledger.</div>";

export class StockLedgerDashboard extends Component {
    static template = "daily_odoo_stock_ledger_report.StockLedgerDashboard";
    
    get dashboardHtml() {
        const activeContext = this._getActiveContext();
        const generatedHtml = activeContext.stock_ledger_dashboard_html || FALLBACK_HTML_MESSAGE;
        
        return markup(generatedHtml);
    }

    _getActiveContext() {
        if (this.env.searchModel?.context) {
            return this.env.searchModel.context;
        }
        
        if (this.env.config?.context) {
            return this.env.config.context;
        }
        
        if (this.env.action?.context) {
            return this.env.action.context;
        }
        
        return {};
    }
}

export class StockLedgerDashboardRenderer extends ListRenderer {
    static template = "daily_odoo_stock_ledger_report.StockLedgerListView";
    static components = { ...ListRenderer.components, StockLedgerDashboard };
}

export const StockLedgerDashboardListView = {
    ...listView,
    Renderer: StockLedgerDashboardRenderer,
};

registry.category("views").add("stock_ledger_dashboard_list", StockLedgerDashboardListView);
