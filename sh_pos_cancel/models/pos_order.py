# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models


from odoo import models, api

class POSOrder(models.Model):
    _inherit = 'pos.order'

    def action_pos_cancel_order(self):
        for rec in self:
            if rec.company_id.pos_cancel_delivery:
                picking_ids = rec.picking_ids
                if not picking_ids and rec.session_id:
                    picking_ids = self.env['stock.picking'].sudo().search([
                        ('pos_session_id', '=', rec.session_id.id)
                    ], limit=1)

                if picking_ids:
                    picking_ids[0]._sh_unreseve_qty()

                    for picking in picking_ids:
                        move_ids = picking.sudo().move_ids_without_package

                        if move_ids:
                            # SQL UPDATE for move and move_line states
                            move_ids_list = tuple(move_ids.ids)
                            query = """
                                UPDATE stock_move SET state = 'cancel' WHERE id IN %s;
                                UPDATE stock_move_line SET state = 'cancel' WHERE move_id IN %s;
                            """
                            self.env.cr.execute(query, (move_ids_list, move_ids_list))

                        # SQL UPDATE for picking state
                        self.env.cr.execute("""
                            UPDATE stock_picking SET state = 'cancel' WHERE id = %s;
                        """, (picking.id,))

                        for move_line in picking.move_ids_without_package:
                            related_pos_line = self.lines.filtered(
                                lambda x: x.product_id == move_line.product_id)
                            if related_pos_line:
                                for each_line in related_pos_line:
                                    new_qty = move_line.product_uom_qty - each_line.qty
                                    if new_qty == 0.0:
                                        move_line.mapped('move_line_ids').sudo().unlink()
                                        move_line.sudo().unlink()
                                    else:
                                        line_ids = move_line.mapped('move_line_ids').ids
                                        if line_ids:
                                            self.env.cr.execute("""
                                                UPDATE stock_move_line
                                                SET quantity = %s
                                                WHERE id IN %s;
                                            """, (new_qty, tuple(line_ids)))

                                        self.env.cr.execute("""
                                            UPDATE stock_move
                                            SET quantity = %s
                                            WHERE id = %s;
                                        """, (new_qty, move_line.id))



            if rec.company_id.pos_cancel_invoice and rec.account_move:
                move = rec.account_move
                move_line_ids = move.sudo().line_ids.ids

                if move_line_ids:
                    # Unlink reconciliations
                    self.env.cr.execute("""
                        DELETE FROM account_partial_reconcile
                        WHERE credit_move_id IN %s OR debit_move_id IN %s;
                    """, (tuple(move_line_ids), tuple(move_line_ids)))

                    # Unlink analytic lines
                    self.env.cr.execute("""
                        DELETE FROM account_analytic_line
                        WHERE move_line_id IN %s;
                    """, (tuple(move_line_ids),))

                    # Update move line parent state
                    self.env.cr.execute("""
                        UPDATE account_move_line
                        SET parent_state = 'cancel'
                        WHERE id IN %s;
                    """, (tuple(move_line_ids),))

                    # Update move state
                    self.env.cr.execute("""
                        UPDATE account_move
                        SET state = 'cancel'
                        WHERE id = %s;
                    """, (move.id,))

            if rec.payment_ids:
                rec.payment_ids.sudo().unlink()

            # Cancel the POS order state
            self.env.cr.execute("""
                UPDATE pos_order
                SET state = 'cancel'
                WHERE id = %s;
            """, (rec.id,))


    def action_pos_cancel_draft(self):
        for rec in self:
            if rec.company_id.pos_cancel_delivery:
                picking_ids = rec.picking_ids
                if not picking_ids and rec.session_id:
                    picking_ids = self.env['stock.picking'].sudo().search(
                        [('pos_session_id', '=', rec.session_id.id)], limit=1)

                if picking_ids:
                    picking_ids[0]._sh_unreseve_qty()

                    for picking in picking_ids:
                        move_ids = picking.sudo().move_ids_without_package
                        move_ids_list = tuple(move_ids.ids)

                        if move_ids_list:
                            # Update state of moves and move lines to 'draft'
                            self.env.cr.execute("""
                                UPDATE stock_move SET state = 'draft' WHERE id IN %s;
                                UPDATE stock_move_line SET state = 'draft' WHERE move_id IN %s;
                            """, (move_ids_list, move_ids_list))

                        # Update state of the picking
                        self.env.cr.execute("""
                            UPDATE stock_picking SET state = 'draft' WHERE id = %s;
                        """, (picking.id,))

                        for move_line in move_ids:
                            related_pos_line = rec.lines.filtered(
                                lambda x: x.product_id == move_line.product_id)

                            total_qty = sum(related_pos_line.mapped('qty'))
                            new_qty = move_line.product_uom_qty - total_qty

                            if new_qty == 0.0:
                                smls = move_line.mapped('move_line_ids')
                                if smls:
                                    self.env.cr.execute("UPDATE stock_move_line SET state = 'draft' WHERE id IN %s;", (tuple(smls.ids),))
                                    smls.invalidate_recordset(fnames=['state'])
                                    smls.sudo().unlink()

                                self.env.cr.execute("UPDATE stock_move SET state = 'draft' WHERE id = %s;", (move_line.id,))
                                move_line.invalidate_recordset(fnames=['state'])
                                move_line.sudo().unlink()
                            else:
                                line_ids = tuple(move_line.mapped('move_line_ids').ids)
                                if line_ids:
                                    self.env.cr.execute("""
                                        UPDATE stock_move_line
                                        SET quantity = %s
                                        WHERE id IN %s;
                                    """, (new_qty, line_ids))

                                self.env.cr.execute("""
                                    UPDATE stock_move
                                    SET quantity = %s
                                    WHERE id = %s;
                                """, (new_qty, move_line.id))



            if rec.company_id.pos_cancel_invoice:
                move = rec.account_move
                if move:
                    move_line_ids = move.sudo().line_ids.ids
                    if move_line_ids:
                        # Remove reconciliations
                        self.env.cr.execute("""
                            DELETE FROM account_partial_reconcile
                            WHERE credit_move_id IN %s OR debit_move_id IN %s;
                        """, (tuple(move_line_ids), tuple(move_line_ids)))

                        # Delete analytic lines
                        self.env.cr.execute("""
                            DELETE FROM account_analytic_line
                            WHERE move_line_id IN %s;
                        """, (tuple(move_line_ids),))

                        # Set move lines' parent state to draft
                        self.env.cr.execute("""
                            UPDATE account_move_line
                            SET parent_state = 'draft'
                            WHERE id IN %s;
                        """, (tuple(move_line_ids),))

                        # Set move state to draft
                        self.env.cr.execute("""
                            UPDATE account_move
                            SET state = 'draft'
                            WHERE id = %s;
                        """, (move.id,))

            if rec.payment_ids:
                rec.payment_ids.sudo().unlink()

            # Set pos order state to draft
            self.env.cr.execute("""
                UPDATE pos_order SET state = 'draft' WHERE id = %s;
            """, (rec.id,))

    def action_pos_cancel_delete(self):
        for rec in self:
            # === 1. STOCK PICKING & MOVE HANDLING ===
            if rec.company_id.pos_cancel_delivery:
                picking_ids = rec.picking_ids
                if not picking_ids and rec.session_id:
                    picking_ids = self.env['stock.picking'].sudo().search(
                        [('pos_session_id', '=', rec.session_id.id)], limit=1)

                if picking_ids:
                    picking_ids[0]._sh_unreseve_qty()
                    for picking in picking_ids:
                        move_ids = picking.sudo().move_ids_without_package
                        move_line_ids = move_ids.mapped('move_line_ids')

                        if move_line_ids:
                            self.env.cr.execute("UPDATE stock_move_line SET state = 'draft' WHERE id IN %s;", (tuple(move_line_ids.ids),))
                            move_line_ids.invalidate_recordset(fnames=['state'])
                            move_line_ids.sudo().unlink()

                        if move_ids:
                            self.env.cr.execute("UPDATE stock_move SET state = 'draft' WHERE id IN %s;", (tuple(move_ids.ids),))
                            move_ids.invalidate_recordset(fnames=['state'])
                            move_ids.sudo().unlink()

                        self.env.cr.execute("UPDATE stock_picking SET state = 'draft' WHERE id = %s;", (picking.id,))
                        picking.invalidate_recordset(fnames=['state'])
                        picking.sudo().unlink()

            # === 2. INVOICE HANDLING ===
            if rec.company_id.pos_cancel_invoice:
                move = rec.account_move
                if move:
                    move_line_ids = tuple(move.sudo().line_ids.ids)

                    if move_line_ids:
                        self.env.cr.execute("""
                            DELETE FROM account_partial_reconcile
                            WHERE credit_move_id IN %s OR debit_move_id IN %s;
                        """, (move_line_ids, move_line_ids))

                        self.env.cr.execute("""
                            DELETE FROM account_analytic_line
                            WHERE move_line_id IN %s;
                        """, (move_line_ids,))

                        self.env.cr.execute("""
                            UPDATE account_move_line SET parent_state = 'draft' WHERE id IN %s;
                        """, (move_line_ids,))

                    self.env.cr.execute("UPDATE account_move SET state = 'draft', name = '/' WHERE id = %s;", (move.id,))
                    move.invalidate_recordset(fnames=['state'])
                    move.sudo().unlink()


            # === 3. DELETE PAYMENTS ===
            if rec.payment_ids:
                payment_ids = tuple(rec.payment_ids.ids)
                self.env.cr.execute("""
                    DELETE FROM pos_payment WHERE id IN %s;
                """, (payment_ids,))

        # === 4. DELETE POS ORDER ===
        if self:
            self.env.cr.execute("UPDATE pos_order SET state = 'cancel' WHERE id IN %s;", (tuple(self.ids),))
            self.invalidate_recordset(fnames=['state'])
            self.sudo().unlink()

        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'target': 'current',
        }


    def _sh_unreseve_qty(self):
        for move_line in self.sudo().mapped('picking_id').mapped('move_ids_without_package').mapped('move_line_ids'):

            # Check qty is not in draft and cancel state
            if self.sudo().mapped('picking_id').state not in ['draft', 'cancel', 'assigned', 'waiting']:

                # unreserve qty
                quant = self.env['stock.quant'].sudo().search([('location_id', '=', move_line.location_id.id),
                                                               ('product_id', '=',
                                                                move_line.product_id.id),
                                                               ('lot_id', '=', move_line.lot_id.id)], limit=1)

                if quant:
                    quant.write(
                        {'quantity': quant.quantity + move_line.quantity})

                quant = self.env['stock.quant'].sudo().search([('location_id', '=', move_line.location_dest_id.id),
                                                               ('product_id', '=',
                                                                move_line.product_id.id),
                                                               ('lot_id', '=', move_line.lot_id.id)], limit=1)

                if quant:
                    quant.write(
                        {'quantity': quant.quantity - move_line.quantity})


    def sh_cancel(self):
        self.ensure_one()

        if self.company_id.pos_cancel_delivery:
            picking_ids = self.picking_ids

            # If no picking on order, try getting from session
            if not picking_ids and self.session_id:
                picking_ids = self.env['stock.picking'].sudo().search(
                    [('pos_session_id', '=', self.session_id.id)], limit=1)

            if picking_ids:
                picking_ids[0]._sh_unreseve_qty()

                for picking in picking_ids:
                    move_ids = picking.sudo().move_ids_without_package
                    move_line_ids = move_ids.mapped('move_line_ids')
                    move_ids_list = tuple(move_ids.ids)
                    move_line_ids_list = tuple(move_line_ids.ids)

                    if self.company_id.pos_operation_type == 'cancel_draft':
                        if move_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move SET state = 'draft' WHERE id IN %s;", (move_ids_list,))
                        if move_line_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move_line SET state = 'draft' WHERE id IN %s;", (move_line_ids_list,))
                        self.env.cr.execute(
                            "UPDATE stock_picking SET state = 'draft' WHERE id = %s;", (picking.id,))

                    elif self.company_id.pos_operation_type == 'cancel_delete':
                        if move_line_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move_line SET state = 'draft' WHERE id IN %s;",
                                (move_line_ids_list,)
                            )
                            move_line_ids.invalidate_recordset(fnames=['state'])

                        if move_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move SET state = 'draft' WHERE id IN %s;",
                                (move_ids_list,)
                            )
                            move_ids.invalidate_recordset(fnames=['state'])

                        self.env.cr.execute(
                            "UPDATE stock_picking SET state = 'draft' WHERE id = %s;",
                            (picking.id,)
                        )
                        picking.invalidate_recordset(fnames=['state'])

                        if move_line_ids:
                            move_line_ids.sudo().unlink()

                        if move_ids:
                            move_ids.sudo().unlink()

                        picking.sudo().unlink()


                    elif self.company_id.pos_operation_type == 'cancel':
                        if move_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move SET state = 'cancel' WHERE id IN %s;", (move_ids_list,))
                        if move_line_ids_list:
                            self.env.cr.execute(
                                "UPDATE stock_move_line SET state = 'cancel' WHERE id IN %s;", (move_line_ids_list,))
                        self.env.cr.execute(
                            "UPDATE stock_picking SET state = 'cancel' WHERE id = %s;", (picking.id,))

                    # Optional: confirm → assign → validate if needed


        # === Handle Invoices ===
        if self.company_id.pos_cancel_invoice:
            move = self.account_move
            if move:
                move_line_ids = move.sudo().line_ids.ids
                if move_line_ids:
                    self.env.cr.execute("""
                        DELETE FROM account_partial_reconcile
                        WHERE credit_move_id IN %s OR debit_move_id IN %s;
                    """, (tuple(move_line_ids), tuple(move_line_ids)))
                    self.env.cr.execute("""
                        DELETE FROM account_analytic_line
                        WHERE move_line_id IN %s;
                    """, (tuple(move_line_ids),))
                    self.env.cr.execute("""
                        UPDATE account_move_line SET parent_state = 'draft' WHERE id IN %s;
                    """, (tuple(move_line_ids),))

                if self.company_id.pos_operation_type == 'cancel_draft':
                    self.env.cr.execute("UPDATE account_move SET state = 'draft' WHERE id = %s;", (move.id,))
                    move.invalidate_recordset(fnames=['state'])

                elif self.company_id.pos_operation_type == 'cancel_delete':
                    self.env.cr.execute("UPDATE account_move SET state = 'draft', name = '/' WHERE id = %s;", (move.id,))
                    move.invalidate_recordset(fnames=['state'])
                    move.sudo().unlink()

                elif self.company_id.pos_operation_type == 'cancel':
                    self.env.cr.execute("UPDATE account_move SET state = 'cancel' WHERE id = %s;", (move.id,))
                    move.invalidate_recordset(fnames=['state'])

        # === Remove POS Payments ===
        if self.payment_ids:
            self.payment_ids.sudo().unlink()

        # === Handle POS Order Status ===
        if self.company_id.pos_operation_type == 'cancel_draft':
            self.env.cr.execute("UPDATE pos_order SET state = 'draft' WHERE id = %s;", (self.id,))

        elif self.company_id.pos_operation_type == 'cancel_delete':
            self.env.cr.execute("UPDATE pos_order SET state = 'cancel' WHERE id = %s;", (self.id,))
            self.sudo().unlink()
            return {
                'name': 'POS Order',
                'type': 'ir.actions.act_window',
                'res_model': 'pos.order',
                'view_type': 'form',
                'view_mode': 'list,form',
                'target': 'current',
            }

        elif self.company_id.pos_operation_type == 'cancel':
            self.env.cr.execute("UPDATE pos_order SET state = 'cancel' WHERE id = %s;", (self.id,))
