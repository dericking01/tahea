from collections import defaultdict

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL, float_compare, float_is_zero

GROUP_XMLID = 'intercompany_stock_transfer.group_intercompany_transfer'

# Header fields that define *what* is moved *where*. They are frozen once the
# transfer leaves the draft state, because stock operations were generated
# from them.
STRUCTURAL_FIELDS = {
    'source_company_id', 'source_warehouse_id', 'source_location_id',
    'dest_company_id', 'dest_warehouse_id', 'dest_location_id', 'line_ids',
}

# Sign of each movement direction on the quantity sitting in transit.
TRANSIT_SIGN = {'dispatch': 1, 'return': -1, 'receipt': -1, 'dest_return': 1}


class IntercompanyStockTransfer(models.Model):
    _name = 'intercompany.stock.transfer'
    _description = 'Inter-Company Stock Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        'Reference', required=True, copy=False, readonly=True, index='trigram',
        default=lambda self: _('New'))
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_transit', 'In Transit'),
        ('received', 'Received'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, readonly=True, copy=False,
        index=True, tracking=True)

    allowed_company_ids = fields.Many2many(
        'res.company', compute='_compute_allowed_company_ids',
        help='Technical field: companies the current user may select.')
    # `company_id` mirrors the source company. It drives `_check_company_auto`
    # for the source-side fields; the destination side is checked explicitly
    # (a transfer legitimately references two different companies).
    company_id = fields.Many2one(
        'res.company', 'Company', related='source_company_id', store=True, index=True)

    source_company_id = fields.Many2one(
        'res.company', 'Source Company', required=True, tracking=True, index=True,
        default=lambda self: self.env.company)
    source_warehouse_id = fields.Many2one(
        'stock.warehouse', 'Source Warehouse', required=True, tracking=True,
        check_company=True, domain="[('company_id', '=', source_company_id)]")
    source_location_id = fields.Many2one(
        'stock.location', 'Source Location', required=True, tracking=True,
        check_company=True,
        domain="[('usage', '=', 'internal'), ('warehouse_id', '=', source_warehouse_id)]")
    dest_company_id = fields.Many2one(
        'res.company', 'Destination Company', required=True, tracking=True, index=True)
    dest_warehouse_id = fields.Many2one(
        'stock.warehouse', 'Destination Warehouse', required=True, tracking=True,
        domain="[('company_id', '=', dest_company_id)]")
    dest_location_id = fields.Many2one(
        'stock.location', 'Destination Location', required=True, tracking=True,
        domain="[('usage', '=', 'internal'), ('warehouse_id', '=', dest_warehouse_id)]")
    transit_location_id = fields.Many2one(
        'stock.location', 'Transit Location', compute='_compute_transit_location_id')

    scheduled_date = fields.Datetime(
        'Scheduled Date', required=True, default=fields.Datetime.now, tracking=True)
    user_id = fields.Many2one(
        'res.users', 'Responsible', default=lambda self: self.env.user,
        domain="[('share', '=', False)]", tracking=True)
    origin = fields.Char('Reference / Source Document', tracking=True)
    note = fields.Text('Remarks')

    line_ids = fields.One2many(
        'intercompany.stock.transfer.line', 'transfer_id', 'Products', copy=True)
    picking_ids = fields.One2many(
        'stock.picking', 'intercompany_transfer_id', 'Stock Operations', readonly=True)
    dispatch_picking_count = fields.Integer(compute='_compute_picking_counts')
    receipt_picking_count = fields.Integer(compute='_compute_picking_counts')
    return_picking_count = fields.Integer(compute='_compute_picking_counts')
    can_dispatch = fields.Boolean(compute='_compute_workflow_flags')
    can_receive = fields.Boolean(compute='_compute_workflow_flags')

    # Audit trail (in addition to chatter tracking).
    confirm_user_id = fields.Many2one('res.users', 'Confirmed By', readonly=True, copy=False)
    confirm_date = fields.Datetime('Confirmed On', readonly=True, copy=False)
    dispatch_user_id = fields.Many2one('res.users', 'Last Dispatched By', readonly=True, copy=False)
    dispatch_date = fields.Datetime('Last Dispatched On', readonly=True, copy=False)
    receive_user_id = fields.Many2one('res.users', 'Last Received By', readonly=True, copy=False)
    receive_date = fields.Datetime('Last Received On', readonly=True, copy=False)
    cancel_user_id = fields.Many2one('res.users', 'Cancelled By', readonly=True, copy=False)
    cancel_date = fields.Datetime('Cancelled On', readonly=True, copy=False)
    cancel_reason = fields.Text('Cancellation Reason', readonly=True, copy=False, tracking=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The transfer reference must be unique.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends_context('uid')
    def _compute_allowed_company_ids(self):
        for transfer in self:
            transfer.allowed_company_ids = self.env.user.company_ids

    def _compute_transit_location_id(self):
        transit = self._get_transit_location()
        for transfer in self:
            transfer.transit_location_id = transit

    def _compute_picking_counts(self):
        # Counting only (read-only); the pickings themselves stay protected by
        # the stock multi-company record rules when opened.
        groups = self.env['stock.picking'].sudo()._read_group(
            [('intercompany_transfer_id', 'in', self.ids)],
            ['intercompany_transfer_id', 'intercompany_role'], ['__count'])
        counts = {(t.id, role): count for t, role, count in groups}
        for transfer in self:
            transfer.dispatch_picking_count = counts.get((transfer.id, 'dispatch'), 0)
            transfer.receipt_picking_count = counts.get((transfer.id, 'receipt'), 0)
            transfer.return_picking_count = (
                counts.get((transfer.id, 'return'), 0) + counts.get((transfer.id, 'dest_return'), 0))

    @api.depends('state', 'picking_ids.state')
    def _compute_workflow_flags(self):
        for transfer in self:
            transfer.can_dispatch = transfer.state in ('confirmed', 'in_transit') and bool(
                transfer._get_pickings('dispatch', open_only=True))
            transfer.can_receive = transfer.state == 'in_transit' and (
                bool(transfer._get_pickings('receipt', open_only=True))
                or bool(transfer._get_uncovered_transit()))

    # ------------------------------------------------------------------
    # Onchanges: keep the selection chain consistent in the UI
    # ------------------------------------------------------------------
    @api.onchange('source_company_id')
    def _onchange_source_company_id(self):
        if self.source_warehouse_id.company_id != self.source_company_id:
            self.source_warehouse_id = self._default_warehouse(self.source_company_id)
        self._onchange_source_warehouse_id()

    @api.onchange('source_warehouse_id')
    def _onchange_source_warehouse_id(self):
        if not self.source_warehouse_id:
            self.source_location_id = False
        elif self.source_location_id.warehouse_id != self.source_warehouse_id:
            self.source_location_id = self.source_warehouse_id.lot_stock_id

    @api.onchange('dest_company_id')
    def _onchange_dest_company_id(self):
        if self.dest_warehouse_id.company_id != self.dest_company_id:
            self.dest_warehouse_id = self._default_warehouse(self.dest_company_id)
        self._onchange_dest_warehouse_id()

    @api.onchange('dest_warehouse_id')
    def _onchange_dest_warehouse_id(self):
        if not self.dest_warehouse_id:
            self.dest_location_id = False
        elif self.dest_location_id.warehouse_id != self.dest_warehouse_id:
            self.dest_location_id = self.dest_warehouse_id.lot_stock_id

    def _default_warehouse(self, company):
        """Propose the warehouse only when the company has exactly one."""
        if not company:
            return False
        warehouses = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=2)
        return warehouses if len(warehouses) == 1 else False

    # ------------------------------------------------------------------
    # Constraints (server side, independent from the UI domains)
    # ------------------------------------------------------------------
    @api.constrains('source_company_id', 'source_warehouse_id', 'source_location_id',
                    'dest_company_id', 'dest_warehouse_id', 'dest_location_id')
    def _check_companies_warehouses_locations(self):
        # sudo: pure consistency validation of ids already submitted by the
        # caller; nothing is returned to the user.
        for transfer in self.sudo():
            if transfer.source_company_id == transfer.dest_company_id:
                raise ValidationError(_(
                    "Source and destination companies must be different. Use a regular "
                    "internal transfer to move stock inside a single company."))
            for side, company, warehouse, location in (
                (_('source'), transfer.source_company_id, transfer.source_warehouse_id,
                 transfer.source_location_id),
                (_('destination'), transfer.dest_company_id, transfer.dest_warehouse_id,
                 transfer.dest_location_id),
            ):
                if warehouse.company_id != company:
                    raise ValidationError(_(
                        "The %(side)s warehouse %(wh)s does not belong to %(company)s.",
                        side=side, wh=warehouse.display_name, company=company.display_name))
                if location.usage != 'internal' or not location.active:
                    raise ValidationError(_(
                        "The %(side)s location %(loc)s must be an active internal location.",
                        side=side, loc=location.display_name))
                if location.warehouse_id != warehouse or location.company_id != company:
                    raise ValidationError(_(
                        "The %(side)s location %(loc)s does not belong to warehouse %(wh)s.",
                        side=side, loc=location.display_name, wh=warehouse.display_name))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'intercompany.stock.transfer') or _('New')
        transfers = super().create(vals_list)
        transfers._check_ict_permission('both')
        return transfers

    def write(self, vals):
        if STRUCTURAL_FIELDS & set(vals):
            if any(transfer.state != 'draft' for transfer in self):
                raise UserError(_(
                    "Companies, warehouses, locations and products can only be changed while "
                    "the transfer is in draft."))
            self._check_ict_permission('both')
        return super().write(vals)

    def unlink(self):
        for transfer in self:
            if transfer.state not in ('draft', 'cancel') or transfer.sudo().picking_ids:
                raise UserError(_(
                    "Transfer %s has stock operations and cannot be deleted. Cancel or "
                    "archive it instead.", transfer.name))
        return super().unlink()

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------
    def _check_ict_permission(self, scope='both'):
        """Ensure the current user may process these transfers.

        :param scope: which companies the user must be allowed in:
            'both', 'source' or 'dest'.
        """
        if self.env.su:
            return
        user = self.env.user
        if not user.has_group(GROUP_XMLID):
            raise AccessError(_(
                "You are not allowed to process inter-company stock transfers. Ask an "
                "administrator to grant you the 'Allow Inter-Company Stock Transfers' right."))
        allowed = user.company_ids
        for transfer in self.sudo():
            needed = {
                'both': transfer.source_company_id | transfer.dest_company_id,
                'source': transfer.source_company_id,
                'dest': transfer.dest_company_id,
            }[scope]
            missing = needed - allowed
            if missing:
                raise AccessError(_(
                    "Transfer %(name)s requires access to company %(companies)s.",
                    name=transfer.name, companies=', '.join(missing.mapped('name'))))

    def _with_ict_companies(self, records, scope='both'):
        """Return `records` in an environment where the transfer's companies are
        active. `env.companies` raises an AccessError if the user is not
        allowed in one of them, so this never widens the user's rights."""
        companies = self.env['res.company']
        for transfer in self.sudo():
            if scope in ('both', 'source'):
                companies |= transfer.source_company_id
            if scope in ('both', 'dest'):
                companies |= transfer.dest_company_id
        company_ids = list(self.env.companies.ids)
        company_ids += [cid for cid in companies.ids if cid not in company_ids]
        records = records.with_context(allowed_company_ids=company_ids)
        records.env.companies  # noqa: B018 - validates the allowed companies
        return records

    def _lock_for_update(self):
        """Row-lock the transfers so concurrent workflow actions serialize."""
        if self.ids:
            self.env.cr.execute(SQL(
                "SELECT id FROM %s WHERE id IN %s FOR UPDATE",
                SQL.identifier(self._table), tuple(self.ids)))
            self.invalidate_recordset(['state'])

    # ------------------------------------------------------------------
    # Stock helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_transit_location(self):
        return self.env.ref('stock.stock_location_inter_company', raise_if_not_found=False) \
            or self.env['stock.location']

    def _get_move_direction(self, move, transit):
        """Classify a stock move of this transfer relative to the transit location."""
        if move.company_id == self.source_company_id:
            if move.location_dest_id == transit:
                return 'dispatch'
            if move.location_id == transit:
                return 'return'
        elif move.company_id == self.dest_company_id:
            if move.location_id == transit:
                return 'receipt'
            if move.location_dest_id == transit:
                return 'dest_return'
        return False

    def _get_pickings(self, role, open_only=False):
        self.ensure_one()
        pickings = self.sudo().picking_ids.filtered(lambda p: p.intercompany_role == role)
        if open_only:
            pickings = pickings.filtered(lambda p: p.state not in ('done', 'cancel'))
        return pickings.with_env(self.env)

    def _get_balances(self):
        """Aggregate the quantities of every line, in the product's UoM, from the
        stock moves themselves (no separate balance is stored).

        Read-only aggregation in sudo: the moves of both companies are needed
        to compute what is in transit, whatever company is active in the UI.
        """
        transit = self._get_transit_location()
        balances = {}
        for transfer in self.sudo():
            for line in transfer.line_ids:
                bal = {
                    'dispatch': 0.0, 'return': 0.0, 'receipt': 0.0, 'dest_return': 0.0,
                    'reserved': 0.0, 'pending_receipt': 0.0, 'pending_return': 0.0,
                    'transit_lots': defaultdict(float),
                    'pending_lots': defaultdict(float),
                    'lot_records': {},
                    'dispatch_moves': self.env['stock.move'],
                }
                product_uom = line.product_id.uom_id
                for move in line.move_ids:
                    direction = transfer._get_move_direction(move, transit)
                    if not direction or move.state == 'cancel':
                        continue
                    if move.state == 'done':
                        if direction == 'dispatch':
                            bal['dispatch_moves'] |= move
                        for ml in move.move_line_ids:
                            key = ml.lot_id.name or ml.lot_name or ''
                            if ml.lot_id:
                                bal['lot_records'].setdefault(key, ml.lot_id)
                            bal[direction] += ml.quantity_product_uom
                            bal['transit_lots'][key] += TRANSIT_SIGN[direction] * ml.quantity_product_uom
                        continue
                    demand = move.product_uom._compute_quantity(move.product_uom_qty, product_uom)
                    if direction == 'dispatch':
                        bal['reserved'] += move.product_uom._compute_quantity(move.quantity, product_uom)
                    elif direction in ('receipt', 'return'):
                        bal['pending_receipt' if direction == 'receipt' else 'pending_return'] += demand
                        for ml in move.move_line_ids:
                            bal['pending_lots'][ml.lot_id.name or ml.lot_name or ''] += ml.quantity_product_uom
                bal['dispatched_net'] = bal['dispatch'] - bal['return']
                bal['received_net'] = bal['receipt'] - bal['dest_return']
                bal['in_transit'] = bal['dispatched_net'] - bal['received_net']
                balances[line.id] = bal
        return balances

    def _get_uncovered_transit(self, balances=None):
        """Quantities in transit that no open receipt/return operation covers yet.

        :return: {line: {lot_key: (qty in product UoM, stock.lot or empty)}}
        """
        balances = balances or self._get_balances()
        result = {}
        for line in self.sudo().line_ids:
            bal = balances[line.id]
            rounding = line.product_id.uom_id.rounding
            remaining = bal['in_transit'] - bal['pending_receipt'] - bal['pending_return']
            if float_compare(remaining, 0, precision_rounding=rounding) <= 0:
                continue
            lots = {}
            for key, qty in sorted(bal['transit_lots'].items()):
                qty = min(qty - bal['pending_lots'].get(key, 0.0), remaining)
                if float_compare(qty, 0, precision_rounding=rounding) > 0:
                    lots[key] = (qty, bal['lot_records'].get(key, self.env['stock.lot']))
                    remaining -= qty
            if lots:
                result[line.with_env(self.env)] = lots
        return result

    def _partner_for_picking(self, partner_company, picking_company):
        partner = partner_company.sudo().partner_id
        if partner and partner.company_id in (self.env['res.company'], picking_company):
            return partner.id
        return False

    def _get_receipt_unit_cost(self, line, dispatch_moves):
        """Unit cost (destination currency, per product UoM) for the receipt.

        Uses the value actually removed from the source company's stock
        (stock_account valuation layers) when available, otherwise the source
        company's product cost. The value is converted between company
        currencies at the dispatch date.
        """
        self.ensure_one()
        product = line.product_id
        unit_cost = 0.0
        if dispatch_moves and 'stock_valuation_layer_ids' in dispatch_moves._fields:
            layers = dispatch_moves.sudo().stock_valuation_layer_ids
            qty = -sum(layers.mapped('quantity'))
            if not float_is_zero(qty, precision_rounding=product.uom_id.rounding):
                unit_cost = -sum(layers.mapped('value')) / qty
        if not unit_cost:
            unit_cost = product.sudo().with_company(self.source_company_id).standard_price
        src_currency = self.source_company_id.currency_id
        dst_currency = self.dest_company_id.currency_id
        if src_currency != dst_currency:
            date = max(dispatch_moves.mapped('date')) if dispatch_moves else fields.Date.context_today(self)
            unit_cost = src_currency._convert(unit_cost, dst_currency, self.dest_company_id, date)
        return unit_cost

    def _create_transit_picking(self, kind, quantities, balances, origin_moves=None):
        """Create a receipt (transit -> destination) or a return
        (transit -> source) operation for the given quantities, with move
        lines pre-filled with the lots that are physically in transit.

        :param kind: 'receipt' or 'return'
        :param quantities: {line: {lot_key: (qty, lot)}} in product UoM
        :param origin_moves: optional {line id: dispatch moves} this receipt
            mirrors (pricing and chaining); defaults to all dispatch moves.
        """
        self.ensure_one()
        transit = self._get_transit_location()
        if kind == 'receipt':
            company = self.dest_company_id
            warehouse = self.dest_warehouse_id
            picking_type = warehouse.in_type_id
            if warehouse.reception_steps == 'one_step':
                picking_dest = self.dest_location_id
            else:
                # Multi-step reception: enter through the warehouse input and
                # let the native push rules carry the goods to the final
                # (selected) location.
                picking_dest = picking_type.default_location_dest_id or warehouse.lot_stock_id
            final_location = self.dest_location_id
            partner = self._partner_for_picking(self.source_company_id, company)
            origin = self.name
        else:
            company = self.source_company_id
            warehouse = self.source_warehouse_id
            picking_type = warehouse.out_type_id.return_picking_type_id or warehouse.in_type_id
            picking_dest = final_location = self.source_location_id
            partner = self._partner_for_picking(self.dest_company_id, company)
            origin = _('Return of %s', self.name)
        if not picking_type:
            raise UserError(_("No operation type is configured for warehouse %s.", warehouse.display_name))

        move_vals = []
        for line, lots in quantities.items():
            line = line.sudo()
            bal = balances[line.id]
            dispatch_moves = (origin_moves or {}).get(line.id) or bal['dispatch_moves']
            vals = {
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': sum(qty for qty, _lot in lots.values()),
                'location_id': transit.id,
                'location_dest_id': picking_dest.id,
                'location_final_id': final_location.id,
                'company_id': company.id,
                'picking_type_id': picking_type.id,
                'intercompany_line_id': line.id,
                'origin': origin,
                'procure_method': 'make_to_stock',
            }
            if kind == 'receipt':
                vals['price_unit'] = self._get_receipt_unit_cost(line, dispatch_moves)
                vals['move_orig_ids'] = [Command.set(dispatch_moves.ids)]
            elif dispatch_moves:
                # Native return semantics: valued back at the original cost.
                vals['origin_returned_move_id'] = dispatch_moves.sorted('id')[-1].id
            move_vals.append(vals)

        Picking = self._with_ict_companies(self.env['stock.picking'], 'dest' if kind == 'receipt' else 'source')
        picking = Picking.with_company(company).create({
            'picking_type_id': picking_type.id,
            'company_id': company.id,
            'location_id': transit.id,
            'location_dest_id': picking_dest.id,
            'scheduled_date': fields.Datetime.now(),
            'origin': origin,
            'partner_id': partner,
            'intercompany_transfer_id': self.id,
            'move_ids': [Command.create(vals) for vals in move_vals],
        })
        picking.action_confirm()
        # The transit location bypasses reservation: replace whatever was
        # auto-generated by the exact lots/quantities that are in transit.
        for move in picking.move_ids:
            lots = quantities[move.intercompany_line_id.with_env(self.env)]
            commands = [Command.delete(ml.id) for ml in move.move_line_ids]
            for key, (qty, lot) in lots.items():
                ml_vals = move._prepare_move_line_vals(quantity=qty)
                ml_vals['location_id'] = transit.id
                if lot and (not lot.company_id or lot.company_id == company):
                    ml_vals.update(lot_id=lot.id, lot_name=False)
                elif key:
                    # Company-specific lot: recreate it with the same name.
                    ml_vals.update(lot_id=False, lot_name=key)
                commands.append(Command.create(ml_vals))
            move.write({'move_line_ids': commands})
        picking.move_line_ids._apply_putaway_strategy()
        return picking

    def _create_receipt_for_dispatch(self, dispatch_pickings):
        """Create the destination receipt for what has just been dispatched.
        Idempotent: dispatch moves already mirrored by a receipt are skipped."""
        self.ensure_one()
        balances = self._get_balances()
        uncovered = self._get_uncovered_transit(balances)
        new_qty = defaultdict(lambda: defaultdict(float))
        new_moves = defaultdict(lambda: self.env['stock.move'])
        for move in dispatch_pickings.sudo().move_ids:
            if move.state != 'done' or not move.intercompany_line_id:
                continue
            if move.move_dest_ids.filtered(lambda m: m.state != 'cancel'):
                continue
            new_moves[move.intercompany_line_id.id] |= move
            for ml in move.move_line_ids:
                new_qty[move.intercompany_line_id.id][ml.lot_id.name or ml.lot_name or ''] += ml.quantity_product_uom
        to_receive = {}
        for line, lots in uncovered.items():
            capped = {}
            for key, (qty, lot) in lots.items():
                qty = min(qty, new_qty[line.id].get(key, 0.0))
                if float_compare(qty, 0, precision_rounding=line.product_id.uom_id.rounding) > 0:
                    capped[key] = (qty, lot)
            if capped:
                to_receive[line] = capped
        if not to_receive:
            return self.env['stock.picking']
        receipt = self._create_transit_picking('receipt', to_receive, balances, origin_moves=new_moves)
        self._message_log(body=Markup(_("Destination receipt %s created for the dispatched stock.")) % receipt._get_html_link())
        return receipt

    def _check_quantity_integrity(self):
        """Invariants checked after every validation of a linked operation:
        dispatched <= requested, and nothing received or returned beyond what
        is actually in transit (per lot/serial)."""
        balances = self._get_balances()
        for line in self.sudo().line_ids:
            bal = balances[line.id]
            rounding = line.product_id.uom_id.rounding
            requested = line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
            if float_compare(bal['dispatched_net'], requested, precision_rounding=rounding) > 0:
                raise ValidationError(_(
                    "%(product)s: you cannot dispatch more than the requested quantity "
                    "(%(requested)s %(uom)s) on transfer %(name)s.",
                    product=line.product_id.display_name, requested=line.product_uom_qty,
                    uom=line.product_uom_id.name, name=line.transfer_id.name))
            if float_compare(bal['received_net'], 0, precision_rounding=rounding) < 0:
                raise ValidationError(_(
                    "%(product)s: you cannot return more than was received on transfer %(name)s.",
                    product=line.product_id.display_name, name=line.transfer_id.name))
            for key, qty in bal['transit_lots'].items():
                if float_compare(qty, 0, precision_rounding=rounding) < 0:
                    raise ValidationError(_(
                        "%(product)s%(lot)s: you cannot receive or return more than the quantity "
                        "dispatched and still in transit on transfer %(name)s.",
                        product=line.product_id.display_name,
                        lot=key and _(" (lot/serial %s)", key) or '',
                        name=line.transfer_id.name))

    def _sync_state(self):
        """Derive the transfer status from its stock operations."""
        for transfer in self:
            if transfer.state in ('draft', 'cancel'):
                continue
            balances = transfer._get_balances()
            open_dispatch = transfer._get_pickings('dispatch', open_only=True)
            open_receipt = transfer._get_pickings('receipt', open_only=True)
            dispatched = in_transit = False
            for line in transfer.sudo().line_ids:
                rounding = line.product_id.uom_id.rounding
                bal = balances[line.id]
                dispatched |= float_compare(bal['dispatched_net'], 0, precision_rounding=rounding) > 0
                in_transit |= float_compare(bal['in_transit'], 0, precision_rounding=rounding) > 0
            if not dispatched:
                new_state = 'confirmed' if open_dispatch else 'cancel'
            elif open_dispatch or open_receipt or in_transit:
                new_state = 'in_transit'
            else:
                new_state = 'received'
            if new_state == transfer.state:
                continue
            vals = {'state': new_state}
            if new_state == 'cancel':
                vals.update(cancel_user_id=self.env.uid, cancel_date=fields.Datetime.now(),
                            cancel_reason=_("All source operations were cancelled."))
            transfer.write(vals)

    def _ict_after_pickings_done(self, pickings):
        """Called after linked operations are validated (any entry point)."""
        self._check_quantity_integrity()
        now = fields.Datetime.now()
        for transfer in self:
            done = pickings.filtered(
                lambda p: p.sudo().intercompany_transfer_id == transfer and p.state == 'done')
            dispatched = done.filtered(lambda p: p.intercompany_role == 'dispatch')
            received = done.filtered(lambda p: p.intercompany_role == 'receipt')
            if dispatched:
                transfer.write({'dispatch_user_id': self.env.uid, 'dispatch_date': now})
                if transfer.state != 'cancel':
                    transfer._create_receipt_for_dispatch(dispatched)
            if received:
                transfer.write({'receive_user_id': self.env.uid, 'receive_date': now})
            for picking in done:
                transfer._message_log(body=Markup(_("%(picking)s (%(role)s) validated by %(user)s.")) % {
                    'picking': picking._get_html_link(),
                    'role': dict(picking._fields['intercompany_role']._description_selection(self.env)).get(
                        picking.intercompany_role, ''),
                    'user': self.env.user.name,
                })
        self._sync_state()

    def _apply_lot_preferences(self, pickings):
        """Reserve the lot requested on the line, if any."""
        for move in pickings.move_ids:
            lot = move.intercompany_line_id.sudo().lot_id
            if not lot or move.picked or move.state in ('done', 'cancel'):
                continue
            if move.move_line_ids and all(ml.lot_id == lot for ml in move.move_line_ids):
                continue
            move._do_unreserve()
            move._update_reserved_quantity(move.product_qty, move.location_id, lot_id=lot, strict=False)
            move._recompute_state()

    def _check_ready_to_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one product to transfer %s.", self.name))
        transit = self._get_transit_location()
        if not transit or not transit.sudo().active:
            raise UserError(_(
                "The 'Inter-company transit' location is not available. It is activated "
                "automatically when a second company is created."))
        if not self.source_warehouse_id.out_type_id:
            raise UserError(_("Warehouse %s has no delivery operation type.", self.source_warehouse_id.display_name))
        if not self.dest_warehouse_id.sudo().in_type_id:
            raise UserError(_("Warehouse %s has no receipt operation type.", self.dest_warehouse_id.sudo().display_name))
        self._check_companies_warehouses_locations()
        self.line_ids._check_line_validity()

    def _create_dispatch_picking(self):
        self.ensure_one()
        transit = self._get_transit_location()
        picking_type = self.source_warehouse_id.out_type_id
        Picking = self._with_ict_companies(self.env['stock.picking'], 'source')
        picking = Picking.with_company(self.source_company_id).create({
            'picking_type_id': picking_type.id,
            'company_id': self.source_company_id.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': transit.id,
            'scheduled_date': self.scheduled_date,
            'origin': self.name,
            'partner_id': self._partner_for_picking(self.dest_company_id, self.source_company_id),
            'intercompany_transfer_id': self.id,
            'move_ids': [Command.create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom_id.id,
                'product_uom_qty': line.product_uom_qty,
                'location_id': self.source_location_id.id,
                'location_dest_id': transit.id,
                'company_id': self.source_company_id.id,
                'picking_type_id': picking_type.id,
                'intercompany_line_id': line.id,
                'origin': self.name,
                'date': self.scheduled_date,
                'procure_method': 'make_to_stock',
            }) for line in self.line_ids],
        })
        picking.action_confirm()
        picking.action_assign()
        self._apply_lot_preferences(picking)
        self._message_log(body=Markup(_("Source operation %s created.")) % picking._get_html_link())
        return picking

    # ------------------------------------------------------------------
    # Workflow actions (buttons)
    # ------------------------------------------------------------------
    def action_confirm(self):
        self._check_ict_permission('both')
        self._lock_for_update()
        for transfer in self:
            if transfer.state != 'draft':
                continue  # idempotent: already confirmed by a concurrent/repeated call
            transfer._check_ready_to_confirm()
            if not transfer._get_pickings('dispatch').filtered(lambda p: p.state != 'cancel'):
                transfer._create_dispatch_picking()
            transfer.write({
                'state': 'confirmed',
                'confirm_user_id': self.env.uid,
                'confirm_date': fields.Datetime.now(),
            })
        return True

    def action_check_availability(self):
        self._check_ict_permission('both')
        for transfer in self:
            pickings = transfer._with_ict_companies(transfer._get_pickings('dispatch', open_only=True), 'source')
            if not pickings:
                raise UserError(_("There is no source operation left to reserve on %s.", transfer.name))
            pickings.action_assign()
            transfer._apply_lot_preferences(pickings)
        return True

    def action_dispatch(self):
        self.ensure_one()
        self._check_ict_permission('both')
        if self.state not in ('confirmed', 'in_transit'):
            raise UserError(_("Only confirmed transfers can be dispatched."))
        pickings = self._get_pickings('dispatch', open_only=True)
        if not pickings:
            raise UserError(_("There is nothing left to dispatch on %s.", self.name))
        pickings = pickings.filtered(lambda p: any(
            not float_is_zero(m.quantity, precision_rounding=m.product_uom.rounding) for m in p.move_ids))
        if not pickings:
            raise UserError(_(
                "No quantity is reserved on the source operation of %s. Use 'Check "
                "Availability' or set the quantities on the source operation.", self.name))
        res = self._with_ict_companies(pickings).button_validate()
        return res if isinstance(res, dict) else True

    def action_receive(self):
        self.ensure_one()
        self._check_ict_permission('dest')
        if self.state != 'in_transit':
            raise UserError(_("Only transfers in transit can be received."))
        pickings = self._get_pickings('receipt', open_only=True)
        if not pickings:
            uncovered = self._get_uncovered_transit()
            if not uncovered:
                raise UserError(_("There is nothing in transit to receive on %s.", self.name))
            pickings = self._create_transit_picking('receipt', uncovered, self._get_balances())
        res = self._with_ict_companies(pickings, 'dest').button_validate()
        return res if isinstance(res, dict) else True

    def action_cancel(self):
        self._check_ict_permission('both')
        if any(transfer.state in ('received', 'cancel') for transfer in self):
            raise UserError(_(
                "Received or cancelled transfers cannot be cancelled. Use a native return on "
                "the destination receipt to send goods back."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Transfer'),
            'res_model': 'intercompany.stock.transfer.cancel',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transfer_ids': [Command.set(self.ids)]},
        }

    def _action_cancel(self, reason):
        """Cancel open operations. Stock already in transit is never silently
        reversed: a return operation (transit -> source) is created and must be
        validated like any other stock operation."""
        self._check_ict_permission('both')
        self._lock_for_update()
        returns = self.env['stock.picking']
        for transfer in self:
            if transfer.state in ('received', 'cancel'):
                raise UserError(_("Transfer %s cannot be cancelled anymore.", transfer.name))
            open_pickings = (transfer._get_pickings('dispatch', open_only=True)
                             | transfer._get_pickings('receipt', open_only=True))
            if open_pickings:
                transfer._with_ict_companies(open_pickings).with_context(ict_skip_sync=True).action_cancel()
            body = _("Transfer cancelled. Reason: %s", reason)
            balances = transfer._get_balances()
            uncovered = transfer._get_uncovered_transit(balances)
            if uncovered:
                return_picking = transfer._create_transit_picking('return', uncovered, balances)
                returns |= return_picking
                body = Markup("%s<br/>%s") % (body, Markup(_(
                    "Stock already in transit must be returned with %s.")) % return_picking._get_html_link())
            transfer.write({
                'state': 'cancel',
                'cancel_user_id': self.env.uid,
                'cancel_date': fields.Datetime.now(),
                'cancel_reason': reason,
            })
            transfer._message_log(body=body)
        return returns

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def _action_view_pickings(self, roles, name):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        pickings = self.env['stock.picking'].sudo().search(
            [('intercompany_transfer_id', '=', self.id), ('intercompany_role', 'in', roles)])
        action.update({
            'name': name,
            'domain': [('id', 'in', pickings.ids)],
            'context': {'create': False},
        })
        if len(pickings) == 1:
            action.update({
                'view_mode': 'form',
                'views': [(self.env.ref('stock.view_picking_form').id, 'form')],
                'res_id': pickings.id,
            })
        return action

    def action_view_dispatch_pickings(self):
        return self._action_view_pickings(['dispatch'], _('Source Operations'))

    def action_view_receipt_pickings(self):
        return self._action_view_pickings(['receipt'], _('Destination Receipts'))

    def action_view_return_pickings(self):
        return self._action_view_pickings(['return', 'dest_return'], _('Returns'))
