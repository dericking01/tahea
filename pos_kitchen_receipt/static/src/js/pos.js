import { patch } from "@web/core/utils/patch";

import "@pos_restaurant/overrides/components/product_screen/actionpad_widget/actionpad_widget";

import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";

import "@pos_restaurant/overrides/models/pos_store";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { changesToOrder, getOrderChanges } from "@point_of_sale/app/models/utils/order_change";

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";



export class kitchenReceipt extends Component {
    static template = "pos_kitchen_receipt.kitchenReceipt";
    static components = {
    };
    static props = {
        data: Object,
    };
    omit(...args) {
        return omit(...args);
    }
}

patch(ActionpadWidget.prototype, {
    async submitOrder() {
        if(this.pos.config.allow_kitchens_receipt){
            await this.pos.sendOrderInPreparation2(this.currentOrder);
        }
        else{
            await this.pos.sendOrderInPreparationUpdateLastChange(this.currentOrder);
        }
    },
});

 patch(PosStore.prototype, {
    async getRenderedReceipt2(order, title, lines, fullReceipt = false, diningModeUpdate) {
        let time;
        if (order.write_date) {
            time = order.write_date?.split(" ")[1].split(":");
            time = time[0] + "h" + time[1];
        }

        const printingChanges = {
            table_name: order.table_id ? order.table_id.table_number : "",
            config_name: order.config.name,
            time: order.write_date ? time : "",
            tracking_number: order.tracking_number,
            takeaway: order.config.takeaway && order.takeaway,
            employee_name: order.employee_id?.name || order.user_id?.name,
            order_note: order.general_note,
            diningModeUpdate: diningModeUpdate,
        };

        const receipt =  {
            operational_title: title,
            changes: printingChanges,
            changedlines: lines,
            fullReceipt: fullReceipt,
        };

        return receipt;
    },
    async sendOrderInPreparation2(order, cancelled = false) {
        // if (this.printers_category_ids_set.size) {
        //     try {
                const orderChange = changesToOrder(
                    order,
                    false,
                    this.orderPreparationCategories,
                    cancelled
                );
                await this.printChanges2(order, orderChange);

                this.showScreen('KitchenReceiptScreenWidget',{"data":order.receipt_val})
            // } catch (e) {
            //     console.info("Failed in printing the changes in the order", e);
            // }
        // }

        order.updateLastOrderChange();
    },
    async printReceipts2(order, printer, title, lines, fullReceipt = false, diningModeUpdate) {
        const receipt = await this.getRenderedReceipt2(
            order,
            title,
            lines,
            fullReceipt,
            diningModeUpdate
        );
        return receipt;

        // const result = await printer.printReceipt(receipt);
        // return result.successful;
    },
    async printChanges2(order, orderChange) {
        // let isPrinted = false;
        var receipt = [];
        const unsuccedPrints = [];
        const isPartOfCombo = (line) =>
            line.isCombo || this.models["product.product"].get(line.product_id).type == "combo";
        const comboChanges = orderChange.new.filter(isPartOfCombo);
        const normalChanges = orderChange.new.filter((line) => !isPartOfCombo(line));
        normalChanges.sort((a, b) => {
            const sequenceA = a.pos_categ_sequence;
            const sequenceB = b.pos_categ_sequence;
            if (sequenceA === 0 && sequenceB === 0) {
                return a.pos_categ_id - b.pos_categ_id;
            }

            return sequenceA - sequenceB;
        });
        orderChange.new = [...comboChanges, ...normalChanges];

        for (const printer of this.unwatched.printers) {
            const changes = this._getPrintingCategoriesChanges(
                printer.config.product_categories_ids,
                orderChange
            );
            const anyChangesToPrint = changes.new.length;
            const diningModeUpdate = orderChange.modeUpdate;
            if (diningModeUpdate || anyChangesToPrint) {
                const printed = await this.printReceipts2(
                    order,
                    printer,
                    "New",
                    changes.new,
                    true,
                    diningModeUpdate
                );
                changes.new = [];
                receipt.push(printed);
            }

            // Print all receipts related to line changes
            const toPrintArray = this.preparePrintingData(order, changes);
            for (const [key, value] of Object.entries(toPrintArray)) {
                const printed = await this.printReceipts2(order, printer, key, value, false);
                 receipt.push(printed);

            }
            // Print Order Note if changed
            // if (orderChange.generalNote && anyChangesToPrint) {
            //     const printed = await this.printReceipts(order, printer, "Message", []);
            //     receipt.push(printed);
            // }
        }
        var order = this.get_order();
        order.receipt_val = receipt;
        // printing errors
        // if (unsuccedPrints.length) {
        //     const failedReceipts = unsuccedPrints.join(", ");
        //     this.dialog.add(AlertDialog, {
        //         title: _t("Printing failed"),
        //         body: _t("Failed in printing %s changes of the order", failedReceipts),
        //     });
        // }

        // return isPrinted;
    }

});

export class KitchenReceiptScreenWidget extends ReceiptScreen {
    static template = "pos_kitchen_receipt.KitchenReceiptScreenWidget";
    static props = {
        ...KitchenReceiptScreenWidget.props,
        data: { type: Object, optional: true },
    };
    setup() {
        super.setup();
        this.pos = usePos();
        this.printer = useService("printer");
    }
    confirm() {
            const { name, props } = this.nextScreen;
            this.pos.showScreen("ProductScreen");
    }
    /**
     * @override
     */
    async printReceipt() {
        // this.buttonPrintReceipt.el.className = "fa fa-fw fa-spin fa-circle-o-notch";
        var order = this.pos.get_order();
        const isPrinted = await this.printer.print(
            kitchenReceipt,
            {
                data:order.receipt_val,


            },
            { webPrintFallback: true }
        );

        // if (isPrinted) {
        //     this.currentOrder._printed = true;
        // }

        // if (this.buttonPrintReceipt.el) {
        //     this.buttonPrintReceipt.el.className = "fa fa-print";
        // }
    }
    get isBill() {
        return true;
    }
}

registry.category("pos_screens").add("KitchenReceiptScreenWidget", KitchenReceiptScreenWidget);

