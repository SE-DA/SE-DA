# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lot_reservation_type = fields.Selection([('1','Całe belki')],'Typ rezerwacji')
    owner_id = fields.Many2one('res.partner', 'Właściciel')

