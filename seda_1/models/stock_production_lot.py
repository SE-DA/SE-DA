# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class ProductionLot(models.Model):
    _inherit = "stock.production.lot"

    @api.depends('quant_ids')
    def _get_pq(self):
        locs = self.env['stock.location'].search([('parent_path', 'ilike', '1/7/8/%')])
        locs_ids = [x.id for x in locs]
        for lot in self:
            quants = self.env['stock.quant'].search([
                ('quantity', '>', 0),
                ('lot_id', '=', lot.id),
                # ('reserved_quantity', '=', 0),
                ('product_id', '=', lot.product_id.id),
                ('location_id', 'in', locs_ids),
            ], order='quantity desc', limit=1)

            if quants and quants.quantity>quants.reserved_quantity:
                lot.positive_q = True
            else:
                lot.positive_q = False
        return False

    positive_q = fields.Boolean('PQ', compute='_get_pq',store=True)
    lead_id = fields.Many2one('crm.lead','Komisja')
    owner_id = fields.Many2one('res.partner', 'Właściciel')


class MrpProductProduce(models.TransientModel):
    _inherit = "mrp.product.produce"

    lead_id = fields.Many2one(related='production_id.lead_id', readonly=True, store=False)
    owner_id = fields.Many2one(related='production_id.owner_id', readonly=True, store=False)
