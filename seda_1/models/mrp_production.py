# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class MrpProduction(models.Model):
    _description = 'Production'
    _inherit = 'mrp.production'

    def _get_so(self):
        sm_rec = self.env['stock.move'].search([
            ('created_production_id', '=', self.id),
        ])
        if sm_rec:
            self.write({'sol_id': sm_rec.sale_line_id.id})
            if sm_rec.sale_line_id.bom_id:
                self.write({'bom_id':sm_rec.sale_line_id.bom_id.id})
            return sm_rec.sale_line_id
        else:
            self.write({'sol_id': False})
        return False

    def _get_lead(self):
        if self.sol_id:
            self.lead_id = self.sol_id.order_id.opportunity_id.id
        return False

    def _get_owner(self):
        if self.sol_id:
            self.lead_id = self.sol_id.order_id.partner_id.id
        return False


    so_id = fields.Many2one('sale.order','SO', related='sol_id.order_id')
    sol_id = fields.Many2one('sale.order.line', 'SOL', compute='_get_so')
    owner_id = fields.Many2one('res.partner', 'Właściciel', related='sol_id.order_id.partner_id')
    lead_id = fields.Many2one('crm.lead', 'Komisja', related='sol_id.order_id.opportunity_id')

    def button_mark_done(self):
        res = super(MrpProduction, self).button_mark_done()
        group_id = self.procurement_group_id.id
        picking_id = False
        lot_ids = []
        if group_id:
            move_ids1 = self.env['stock.move'].search([('group_id', '=', group_id)])
            if move_ids1:
                move_ids = [x.id for x in move_ids1]
                lot_ids1 = self.env['stock.move.line'].search(['&',('move_id', 'in', move_ids),('product_id','!=',self.product_id.id)])
                for sm in lot_ids1:
                    if sm.lot_id and sm.lot_id.id not in lot_ids:
                        lot_ids.append(sm.lot_id.id)
                if lot_ids:
                    for lot in lot_ids:
                        lot_rec = self.env['stock.production.lot'].browse(lot)
                        quants = self.env['stock.quant'].search([
                            ('quantity', '>', 0),
                            ('lot_id', '=', lot_rec.id),
                            ('product_id', '=', lot_rec.product_id.id),
                            ('location_id', '=', 17),
                        ], order='quantity desc', limit=1)
                        if quants:
                            if not picking_id:
                                picking = self.env['stock.picking'].create({
                                    'location_id': quants.location_id.id,
                                    'location_dest_id': 8,
                                    'picking_type_id': 5,
                                    'name':self.name+'-R',
                                })
                                picking_id = picking.id
                            values = {
                                    'lot_name':lot_rec.name,
                                    'lot_id':lot_rec.id,
                                    'reference': self.name+'-R',
                                    'product_id': lot_rec.product_id.id,
                                    'product_uom_id': quants.product_uom_id.id,
                                    'product_uom_qty': quants.quantity,
                                    'location_id': quants.location_id.id,
                                    'location_dest_id': 8,
                                    # 'group_id': group_id,
                                    # 'origin': self.name,
                                    'picking_id': picking_id,
                                    # 'state': 'waiting',
                                    'company_id': self.company_id.id,
                                    'owner_id':lot_rec.owner_id.id
                                }
                            move_id = self.env['stock.move.line'].create(values)
                            self.env['stock.quant']._update_reserved_quantity(
                                lot_rec.product_id, quants.location_id, quants.quantity, lot_id=lot_rec,
                                package_id=False, owner_id=lot_rec.owner_id, strict=True
                            )

        return res


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    lot_id = fields.Many2one('stock.production.lot', 'LOT')
