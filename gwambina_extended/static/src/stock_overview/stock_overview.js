/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { StockKanbanRenderer } from "@stock/components/stock_overview/stock_overview";

StockKanbanRenderer.template = "gwambina_extended.StockKanbanRenderer";

patch(StockKanbanRenderer.prototype, {
    setup() {
        super.setup();
        this.gwOrm = useService("orm");
        this.gwAction = useService("action");
        this.gwCustomReceipts = useState({ show: false, type_count: 0, ready: 0, waiting: 0, late: 0 });
        onWillStart(async () => {
            const context = this.props.list.context || {};
            if (
                this.env.inDialog ||
                this.props.list.resModel !== "stock.picking.type" ||
                context.gw_hide_custom_receipts_card
            ) {
                return;
            }
            const data = await this.gwOrm.call("stock.picking.type", "gw_get_custom_receipts_data", []);
            Object.assign(this.gwCustomReceipts, data);
        });
    },

    async gwOpenCustomReceiptTypes() {
        const action = await this.gwOrm.call("stock.picking.type", "gw_action_custom_receipts", []);
        await this.gwAction.doAction(action);
    },

    async gwOpenCustomReceiptPickings(state) {
        const action = await this.gwOrm.call(
            "stock.picking.type",
            "gw_action_custom_receipts_pickings",
            [],
            { state: state || false }
        );
        await this.gwAction.doAction(action);
    },
});
