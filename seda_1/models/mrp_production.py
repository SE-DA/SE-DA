# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class MrpProduction(models.Model):
    _description = 'Production'
    _inherit = 'mrp.production'

    @api.model
    def _get_so(self):
        sm_rec = self.env['stock.move'].search([
            ('created_production_id', '=', self.id),
        ])
        if sm_rec:
            self.sol_id = sm_rec.sale_line_id.id
            if sm_rec.sale_line_id.bom_id:
                self.write({'bom_id':sm_rec.sale_line_id.bom_id.id})
        return False


    # so_id = fields.Many2one('sale.order','SO', related='sol_id.order_id')
    sol_id = fields.Many2one('sale.order.line', 'SOL', compute='_get_so')
    owner_id = fields.Many2one('res.partner', 'Właściciel', related='sol_id.order_id.partner_id')
    lead_id = fields.Many2one('crm.lead', 'Komisja', related='sol_id.order_id.opportunity_id')


