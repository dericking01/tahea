"""Destination dropdowns for sibling branches the user is not allowed in.

A branch user may send stock to the other branches of its company without
being allowed in them (see `_get_delegated_companies`). Record rules hide those
branches, so the transfer form's destination fields pass the
`ict_delegated_targets` context key and the suggestions are extended here with
the matching companies, warehouses and *internal* locations of those branches
only.

* The key is only a switch. The set of branches is recomputed server-side from
  the user's own companies; ids coming from the client are never trusted.
* Only `id` and display name are returned (what `name_search` always returns).
  Nothing else of those branches becomes readable: stock, quants, pickings and
  warehouse/location records stay protected by the native record rules.
"""
from odoo import api, models
from odoo.osv import expression


def _with_delegated(model, results, name, domain, operator, limit, target_domain):
    if model.env.su or not model.env.context.get('ict_delegated_targets'):
        return results
    companies = model.env['intercompany.stock.transfer']._get_delegated_companies()
    if not companies:
        return results
    remaining = None if limit is None else limit - len(results)
    if remaining is not None and remaining <= 0:
        return results
    full_domain = expression.AND([
        [('display_name', operator, name)] if name else [],
        domain or [],
        target_domain(companies),
        [('id', 'not in', [res[0] for res in results])],
    ])
    extra = model.sudo().search_fetch(full_domain, ['display_name'], limit=remaining)
    return results + [(rec.id, rec.display_name) for rec in extra]


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        results = super().name_search(name, args, operator, limit)
        return _with_delegated(self, results, name, args, operator, limit,
                               lambda companies: [('id', 'in', companies.ids)])


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        results = super().name_search(name, args, operator, limit)
        return _with_delegated(self, results, name, args, operator, limit,
                               lambda companies: [('company_id', 'in', companies.ids)])


class StockLocation(models.Model):
    _inherit = 'stock.location'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        results = super().name_search(name, args, operator, limit)
        return _with_delegated(self, results, name, args, operator, limit, lambda companies: [
            ('company_id', 'in', companies.ids),
            ('usage', '=', 'internal'),
            ('warehouse_id', '!=', False),
        ])
