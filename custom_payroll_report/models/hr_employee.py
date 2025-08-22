from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    nida_number = fields.Char(string='NIDA Number', size=20)
    nssf_number = fields.Char(string='NSSF Number', size=20)
    tin_number = fields.Char(string='TIN Number', size=20)
    bank_account_number = fields.Char(string='Bank Account Number', size=30)
