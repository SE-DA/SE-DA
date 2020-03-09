# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class MrpProduction(models.Model):
    _description = 'Production'
    _inherit = 'mrp.production'

    def action_assign(self):
        for production in self:
            bom_line_products = {}
            multiple_use_bom = []
            for line in production.move_raw_ids:
                if line.bom_line_id.product_id.id not in bom_line_products:
                    bom_line_products[line.bom_line_id.product_id.id] = [(line.bom_line_id.lot_id.id,line.bom_line_id.product_qty)]
                else:
                    bom_line_products[line.bom_line_id.product_id.id].append((line.bom_line_id.lot_id.id,line.bom_line_id.product_qty))
                    multiple_use_bom.append(line.bom_line_id.product_id.id)

            for move in production.move_raw_ids:
                if (move.bom_line_id.lot_id.owner_id != self.owner_id and self.state != 'done') or (move.product_id.id in multiple_use_bom and self.state != 'done'):

                    owner_id = move.bom_line_id.lot_id.owner_id
                    if move.product_id.tracking == 'none':
                        owner_id = move.product_id.owner_id
                    available_quantity = self.env['stock.quant']._get_available_quantity(
                        move.product_id, move.location_id, lot_id=move.bom_line_id.lot_id, package_id=False,
                        owner_id=owner_id, strict=True)

                    qty= min(move.product_qty-move.reserved_availability,available_quantity)
                    if qty:
                        sml_obj = self.env['stock.move.line']
                        vals = {'move_id': move.id,
                                'product_id': move.product_id.id,
                                'product_uom_id': move.product_uom.id,
                                'location_id': move.location_id.id,
                                'location_dest_id': move.picking_type_id.default_location_dest_id.id,
                                'picking_id': move.picking_id.id,
                                'product_uom_qty': qty,
                                'lot_id': move.bom_line_id.lot_id.id,
                                'owner_id': owner_id.id,
                                'lead_id': move.bom_line_id.lot_id.lead_id.id,
                                'state': 'assigned'

                                }
                        sm = sml_obj.create(vals)
                        self.env['stock.quant']._update_reserved_quantity(
                            move.product_id, move.location_id, qty, lot_id=move.bom_line_id.lot_id,
                            package_id=False, owner_id=owner_id, strict=True
                        )
                        move.write({'state': 'assigned'})
        res = super(MrpProduction, self).action_assign()
        return res

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
    bomed = fields.Boolean('bomed')

    def button_mark_done(self):
        res = super(MrpProduction, self).button_mark_done()
        group_id = self.procurement_group_id.id
        picking_id = False
        lot_ids = []
        picking = False
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
                            qty = quants.quantity-quants.reserved_quantity
                            if qty <=0:
                                continue
                            if not picking_id:
                                picking = self.env['stock.picking'].create({
                                    'location_id': quants.location_id.id,
                                    'location_dest_id': 8,
                                    'picking_type_id': 5,
                                    'name':self.name+'-R',
                                    # 'state': 'confirmed',
                                })
                                picking_id = picking.id
                            values = {
                                    'lot_name':lot_rec.name,
                                    'lot_id':lot_rec.id,
                                    'reference': self.name+'-R',
                                    'product_id': lot_rec.product_id.id,
                                    'product_uom_id': quants.product_uom_id.id,
                                    'product_uom_qty': qty,
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
                                lot_rec.product_id, quants.location_id, qty, lot_id=lot_rec,
                                package_id=False, owner_id=lot_rec.owner_id, strict=True
                            )
                    if picking:
                        picking.write({'state':'confirmed'})

        return res

    def write(self, vals):
        bom_line_products = {}
        multiple_use_bom = []
        for line in self.move_raw_ids:
            if line.bom_line_id.product_id.id not in bom_line_products:
                bom_line_products[line.bom_line_id.product_id.id] = [
                    (line.bom_line_id.lot_id.id, line.bom_line_id.product_qty)]
            else:
                bom_line_products[line.bom_line_id.product_id.id].append(
                    (line.bom_line_id.lot_id.id, line.bom_line_id.product_qty))
                multiple_use_bom.append(line.bom_line_id.product_id.id)
        if multiple_use_bom and self.reservation_state == 'assigned' and self.state!='done'  and not self.bomed:
            sm_rec = self.env['stock.move'].search([
                ('created_production_id', '=', self.id),
            ])
            vals['bomed'] = True
            if sm_rec:
                vals['sol_id'] =  sm_rec.sale_line_id.id
                vals['lead_id'] = sm_rec.sale_line_id.order_id.opportunity_id.id
                vals['lead_id'] = sm_rec.sale_line_id.order_id.partner_id.id
                if sm_rec.sale_line_id.bom_id:
                   vals['bom_id']= sm_rec.sale_line_id.bom_id.id
            self.button_unreserve()
            self.action_assign()
            # self._get_so()
            # self._get_lead()
            # self._get_owner()


        res = super(MrpProduction, self).write(vals)


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    lot_id = fields.Many2one('stock.production.lot', 'LOT')
