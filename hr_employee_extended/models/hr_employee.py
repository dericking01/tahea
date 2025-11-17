from odoo import models, fields

class HrEmployeeExtended(models.Model):
    _inherit = 'hr.employee'
    
    tin_number = fields.Char(
        string='TIN Number',
        help='Tax Identification Number',
        tracking=True,
        index=True # Adds database index for better search performance
    )
    
    nssf_number = fields.Char(
        string='NSSF Number',
        help='National Social Security Fund Number',
        tracking=True,
        index=True
    )

class hr_custom(models.Model):
    _inherit = 'hr.contract'

    
    heslb = fields.Boolean("Loan Board", default=True)
    nhif_2 = fields.Boolean("NHIF", default=True)
    paye = fields.Boolean("PAYE", default=True)