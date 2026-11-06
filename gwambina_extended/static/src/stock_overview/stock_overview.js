/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatInteger } from "@web/views/fields/formatters";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { StockKanbanRenderer } from "@stock/components/stock_overview/stock_overview";

StockKanbanRenderer.template = "gwambina_extended.StockKanbanRenderer";

patch(StockKanbanRenderer.prototype, {
    setup() {
        super.setup();
        this.gwOrm = useService("orm");
        this.gwAction = useService("action");
        this.gwCustomReceipts = useState({ show: false });
        // Same summary as the standard operation type cards (e.g. Delivery Orders)
        this.gwSummaryLinks = [
            { key: "waiting", label: _t("Waiting") },
            { key: "late", label: _t("Late") },
            { key: "backorders", label: _t("Back Orders") },
            { key: "operations", label: _t("Operations") },
        ];
        onWillStart(async () => {
            if (this.env.inDialog || this.props.list.resModel !== "stock.picking.type") {
                return;
            }
            const data = await this.gwOrm.call("stock.picking.type", "gw_get_custom_receipts_data", []);
            Object.assign(this.gwCustomReceipts, data);
        });
    },

    gwFormat(value) {
        return formatInteger(value);
    },

    async gwOpenCustomReceipts(filterKey) {
        const action = await this.gwOrm.call(
            "stock.picking.type",
            "gw_action_custom_receipts",
            [],
            { filter_key: filterKey || false }
        );
        await this.gwAction.doAction(action);
    },
});
