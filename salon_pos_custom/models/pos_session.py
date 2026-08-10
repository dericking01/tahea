from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"


    def _load_pos_data_models(self, config_id):

        result = super()._load_pos_data_models(config_id)

        if "hr.employee" not in result:
            result.append("hr.employee")

        return result


    def _load_pos_data_fields(self, config_id):

        result = super()._load_pos_data_fields(config_id)

        if isinstance(result, dict):

            result["hr.employee"] = [
                "id",
                "name",
            ]

        return result