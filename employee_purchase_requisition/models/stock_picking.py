# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import fields, models
from odoo.exceptions import UserError


class Picking(models.Model):
    """Class to add new field in stock picking"""
    _inherit = 'stock.picking'

    state = fields.Selection(selection_add=[('in_transit', 'In Transit')])

    requisition_order = fields.Char(string='Requisition Order', help='Requisition order sequence')

    def button_validate(self):
        for rec in self:
            if rec.state != 'in_transit':
                raise UserError("You can only validate a picking in the In-Transit state.")
        return super().button_validate()


    def action_mark_in_transit(self):
        """Mark picking as In Transit"""
        for picking in self:
            if picking.state != 'assigned':
                continue
            picking.state = 'in_transit'


    
