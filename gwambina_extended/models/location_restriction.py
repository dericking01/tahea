from odoo import api, models
from odoo.osv import expression


class GwLocationRestrictionMixin(models.AbstractModel):
    """ Filters what a location-restricted user sees in list/kanban/pivot/graph views.

    Only the web client entry points are filtered (not ``search``), so stock business logic
    (reservation, quant updates, purchase/sale computations...) keeps working on every record.
    """
    _name = 'gw.location.restriction.mixin'
    _description = 'Stock location visibility restriction'

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return []

    @api.model
    def _gw_restrict_domain(self, domain):
        user = self.env.user
        if self.env.su or not user.restrict_stock_locations:
            return domain
        return expression.AND([domain or [], self._gw_location_restriction_domain(user.allowed_stock_location_ids)])

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(
            self._gw_restrict_domain(domain), specification,
            offset=offset, limit=limit, order=order, count_limit=count_limit)

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        return super().web_read_group(
            self._gw_restrict_domain(domain), fields, groupby,
            limit=limit, offset=offset, orderby=orderby, lazy=lazy)


class StockQuant(models.Model):
    _name = 'stock.quant'
    _inherit = ['stock.quant', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return [('location_id', 'child_of', locations.ids)]


class StockWarehouse(models.Model):
    _name = 'stock.warehouse'
    _inherit = ['stock.warehouse', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return [('view_location_id', 'parent_of', locations.ids)]


class StockPickingType(models.Model):
    _name = 'stock.picking.type'
    _inherit = ['stock.picking.type', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return ['|', '|',
                ('code', 'in', ('internal', 'outgoing')),
                ('warehouse_id', '=', False),
                ('warehouse_id.view_location_id', 'parent_of', locations.ids)]


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return ['|', '|',
                ('picking_type_code', 'in', ('internal', 'outgoing')),
                ('location_id', 'child_of', locations.ids),
                ('location_dest_id', 'child_of', locations.ids)]


class StockMove(models.Model):
    _name = 'stock.move'
    _inherit = ['stock.move', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return ['|', '|',
                ('picking_code', 'in', ('internal', 'outgoing')),
                ('location_id', 'child_of', locations.ids),
                ('location_dest_id', 'child_of', locations.ids)]


class StockMoveLine(models.Model):
    _name = 'stock.move.line'
    _inherit = ['stock.move.line', 'gw.location.restriction.mixin']

    @api.model
    def _gw_location_restriction_domain(self, locations):
        return ['|', '|',
                ('picking_code', 'in', ('internal', 'outgoing')),
                ('location_id', 'child_of', locations.ids),
                ('location_dest_id', 'child_of', locations.ids)]
