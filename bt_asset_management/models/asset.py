# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, tools, models, _
from odoo.exceptions import Warning
from odoo.exceptions import ValidationError
from odoo import tools
import string
from odoo.tools import float_compare

class BtAsset(models.Model):
    _name = "bt.asset"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Asset"


    def _get_default_location(self):
        obj = self.env['bt.asset.location'].search([('default','=',True)])
        if not obj:
            raise Warning(_("Please create asset location first"))
        loc = obj[0]
        return loc

    name = fields.Char(string='Name', required=True)
    purchase_date = fields.Date(string='Purchase Date',track_visibility='always')
    purchase_value = fields.Float(string='Purchase Value', track_visibility='always')
    asset_code = fields.Char(string='Asset Code')
    is_created = fields.Boolean('Created', copy=False)
    current_loc_id = fields.Many2one('bt.asset.location', string="Current Location", default=_get_default_location, required=True)
    model_name = fields.Char(string='Model Name')
    serial_no = fields.Char(string='Serial No', track_visibility='always')
    manufacturer = fields.Char(string='Manufacturer')
    warranty_start = fields.Date(string='Warranty Start')
    warranty_end = fields.Date(string='Warranty End')
    category_id = fields.Many2one('bt.asset.category', string='Category Id')
    note = fields.Text(string='Internal Notes')
    state = fields.Selection([
            ('active', 'Active'),
            ('scrapped', 'Scrapped')], string='State',track_visibility='onchange', default='active', copy=False)

    code_line_ids = fields.One2many('bt.asset.code.line','asset_id', string='Asset Code Line')
    book_value = fields.Float(string='Book Value')
    accrued_interest = fields.Float(string='Accrued Interest')
    market_value = fields.Float(string='Market Value', compute='_market_value')
    current_value = fields.Float(string='Current Value')
    holding_value = fields.Float(string='Holding Value')
    price = fields.Float(string='Price')


    @api.depends('book_value', 'holding_value', 'accrued_interest', 'price')
    def _market_value(self):
        for record in self:
            if record.book_value:
                record.market_value = float(record.book_value + record.accrued_interest)
            else:
                record.market_value = float(record.holding_value * record.price)


    @api.model
    def create(self, vals):
        print('valsvalsvals',vals)
        vals.update({'is_created':True})
        lot = super(BtAsset, self).create(vals)
        lot.message_post(body=_("Asset %s created with asset code %s")% (lot.name,lot.asset_code))
        return lot

    def action_move_vals(self):
        for asset in self:
            location_obj = self.env['bt.asset.location'].search([('default_scrap','=',True)])
            if not location_obj:
                raise Warning(_("Please set scrap location first"))
            move_vals = {
                'from_loc_id' : asset.current_loc_id.id,
                'asset_id' : asset.id,
                'to_loc_id' : location_obj.id
                }
            asset_move = self.env['bt.asset.move'].create(move_vals)
            asset_move.action_move()
            asset.current_loc_id = location_obj.id
            asset.state = 'scrapped'
            if asset.state == 'scrapped':
                asset.message_post(body=_("Scrapped"))
        return True

class BtAssetLocation(models.Model):
    _name = "bt.asset.location"
    _description = "Asset Location"

    name = fields.Char(string='Name', required=True)
    asset_ids = fields.One2many('bt.asset','current_loc_id', string='Assets')
    default = fields.Boolean('Default', copy=False)
    default_scrap = fields.Boolean('Scrap')

    @api.model
    def create(self, vals):
        result = super(BtAssetLocation, self).create(vals)
        obj = self.env['bt.asset.location'].search([('default','=',True)])
        asset_obj = self.env['bt.asset.location'].search([('default_scrap','=',True)])
        if len(obj) > 1 or len(asset_obj) > 1:
            raise ValidationError(_("Default location have already set."))
        return result


    def write(self, vals):
        res = super(BtAssetLocation, self).write(vals)
        obj = self.env['bt.asset.location'].search([('default','=',True)])
        asset_obj = self.env['bt.asset.location'].search([('default_scrap','=',True)])
        if len(obj) > 1 or len(asset_obj) > 1:
            raise ValidationError(_("Default location have already set."))
        return res

class BtAssetCategory(models.Model):
    _name = "bt.asset.category"
    _description = "Asset Category"

    name = fields.Char(string='Name', required=True)
    categ_no = fields.Char(string='Category No')

class BtAssetInvestment(models.Model):
    _name = "bt.asset.investment"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Asset Investment Transactions"


    name = fields.Char(string='Title')
    date = fields.Date(string='Date')
    category_id = fields.Many2one('bt.asset.category', string='Asset Class')
    code_line_ids = fields.One2many('bt.asset.code.line','investment_id', string='Asset Code Line')
    total_credit = fields.Float(string='Total Credit', compute='_compute_total_credit')
    total_debit = fields.Float(string='Total Debit', compute='_compute_total_debit')
    total_balance= fields.Float(string='Total Balance', compute='_compute_total_balance')
    investment_adm = fields.Selection([
                                    ('nicol', 'NICOL'),
                                    ('old', 'OLD MUTUAL'),
                                    ('cont', 'CONTINENTAL'),
                                    ('zamara', 'ZAMARA'),
                                    ], string='Investment Admin', default='zamara')


    @api.depends('code_line_ids.debit')
    def _compute_total_debit(self):
        self.total_debit = sum(line.debit for line in self.code_line_ids)

    @api.depends('code_line_ids.price_cost')
    def _compute_total_credit(self):
        self.total_credit = sum(line.price_cost for line in self.code_line_ids)

    @api.depends('total_credit', 'total_debit')
    def _compute_total_balance(self):
        self.total_balance = float(self.total_debit - self.total_credit)





class BtAssetCode(models.Model):
    _name = "bt.asset.code"
    _description = "Asset Code"

    name = fields.Char(string="Code Name")
    code = fields.Char(string="Code")


class BtAssetCodeLine(models.Model):
    _name = "bt.asset.code.line"
    _description = "Asset Code Line"

    date = fields.Date(string='Date')
    name = fields.Char(string='Label')
    code_id = fields.Many2one('bt.asset.code', string='Code Name')
    price_cost = fields.Float(string='Credit')
    debit = fields.Float(string='Debit')
    asset_id = fields.Many2one('bt.asset')
    investment_id = fields.Many2one('bt.asset.investment')

class BtInv(models.Model):
    _name = "bt.inv"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Inveroment Reports"

    name = fields.Char(string="Title")
    inflation = fields.Char(string="Inflation rate")
    police_rate = fields.Char(string="Police Rate")
    gdp = fields.Char(string="GDP Growth")
    fiscal_deficit = fields.Char(string="Fiscal Depicit")
    fx = fields.Char(string="FX Stability")
    tb = fields.Char(string="TB average rate")
    mass = fields.Char(string="Masi")
    cover = fields.Char(string="Import Cover ( USD)")
    debt = fields.Char(string="Debt Sustainability")
    date = fields.Date("Date")
    remark = fields.Text("Remarks")
    investment_adm = fields.Selection([
                                    ('nicol', 'NICOL'),
                                    ('old', 'OLD MUTUAL'),
                                    ('cont', 'CONTINENTAL'),
                                    ('zamara', 'ZAMARA'),
                                    ], string='Investment Admin', default='zamara')

class BtMix(models.Model):
    _name = "bt.fund.mix"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Fund Mix Reports"

    name = fields.Char(string="Title")
    date = fields.Date(string="Reporting Date")
    category_id = fields.Many2one('bt.asset.category', string='Asset Class')
    omig = fields.Char("OMIG")
    cam = fields.Char("CAM")
    nam = fields.Char("NAM")
    note = fields.Text("Note")
    investment_adm = fields.Selection([
                                    ('nicol', 'NICOL'),
                                    ('old', 'OLD MUTUAL'),
                                    ('cont', 'CONTINENTAL'),
                                    ('zamara', 'ZAMARA'),
                                    ], string='Investment Admin', default='zamara')

class BtReturn(models.Model):
    _name = "bt.return"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Fund Return Reports"

    name = fields.Char(string="Title")
    date = fields.Date(string="Reporting Date")
    gs = fields.Char(string="Government Securities")
    cp = fields.Char(string="Corporate Papers")
    dp = fields.Char(string="Deposits")
    er = fields.Char(string="Equity Return")
    pr = fields.Char(string="Property")
    cr = fields.Char(string="Composite Rate")
    br = fields.Char(string="Benchmark (inflation +5%)")
    overall = fields.Html(string="Overall")
    investment_adm = fields.Selection([
                                    ('nicol', 'NICOL'),
                                    ('old', 'OLD MUTUAL'),
                                    ('cont', 'CONTINENTAL'),
                                    ('zamara', 'ZAMARA'),
                                    ], string='Investment Admin', default='zamara')





# vim:expandtab:smartindent:tabstop=2:softtabstop=2:shiftwidth=2:
