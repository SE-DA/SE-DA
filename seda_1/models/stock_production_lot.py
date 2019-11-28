# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class ProductionLot(models.Model):
    _inherit = "stock.production.lot"

    lead_id = fields.Many2one('crm.lead','Komisja')
    owner_id = fields.Many2one('res.partner', 'Właściciel')


class MrpProductProduce(models.TransientModel):
    _inherit = "mrp.product.produce"

    lead_id = fields.Many2one(related='production_id.lead_id', readonly=True, store=False)
    owner_id = fields.Many2one(related='production_id.owner_id', readonly=True, store=False)
