from odoo import models

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_set_lost(self, **kwargs):
        res = super().action_set_lost(**kwargs)

        lost_stage = self.env['crm.stage'].search([
            ('name', '=', 'Lost')
        ], limit=1)

        if lost_stage:
            self.write({
                'stage_id': lost_stage.id,
                'active': True,
            })

        return res
