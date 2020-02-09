# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_tmpl_id = fields.Many2one('product.template','Prod_tmpl',related='product_id.product_tmpl_id')

    bom_id = fields.Many2one(
        'mrp.bom', 'Bill of Material',
        states={'done': [('readonly', True)]})  # Add domain


class MrpBom(models.Model):
    _inherit = ['mrp.bom']

    @api.onchange('owner_id')
    def _onchange_owner_id(self):
        self.lead_id = False

    lead_id = fields.Many2one('crm.lead', 'Komisja')
    owner_id = fields.Many2one('res.partner', 'Właściciel')
