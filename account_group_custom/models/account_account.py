from odoo import models, fields

class AccountAccount(models.Model):
    _inherit = 'account.account'

    group_id = fields.Many2one(
        'account.group', 
        string='Account Group', 
        compute=False,       
        store=True,          
        readonly=False,
        force_save=True
    )