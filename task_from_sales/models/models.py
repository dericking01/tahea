from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'

    sale_order_id = fields.Many2one('sale.order', string='Sales Order')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('project.project', string="Project")

    def action_create_task(self):
        for order in self:
            # Check if task already exists for this sale order
            existing_task = self.env['project.task'].sudo().search([
                ('sale_order_id', '=', order.id)
            ], limit=1)

            if existing_task:
                raise UserError(f"A task is already created for this Sales Order: {existing_task.name}")

            # Find the project
            project = self.env['project.project'].search([('name', '=', 'Laboratory Task')], limit=1)
            if not project:
                raise UserError("Project 'Laboratory Task' not found. Please create it first.")

            # Prepare task description
            description = '\n'.join([
                f"- {line.product_id.name} - Qty: {line.product_uom_qty}"
                for line in order.order_line
            ])

            # Create the task
            self.env['project.task'].sudo().create({
                'name': f"Task for {order.name}",
                'project_id': project.id,
                'partner_id': order.partner_id.id,
                'sale_order_id': order.id,
                'description': description,
            })

            _logger.info("Task created for Sale Order %s", order.name)
