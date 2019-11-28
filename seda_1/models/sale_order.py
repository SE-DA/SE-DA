# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bom_id = fields.Many2one(
        'mrp.bom', 'Bill of Material',
        states={'done': [('readonly', True)]})  # Add domain


class MrpBom(models.Model):
    _inherit = ['mrp.bom']

    lead_id = fields.Many2one('crm.lead', 'Komisja')
    owner_id = fields.Many2one('res.partner', 'Właściciel')
