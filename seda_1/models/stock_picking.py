# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime


class Picking(models.Model):
    _inherit = "stock.picking"

    # @api.model
    def _get_so(self):
        lead_id = False
        owner_id = False
        so_id = False
        if self.sale_id:
            if self.sale_id.opportunity_id:
                lead_id = self.sale_id.opportunity_id.id
            owner_id = self.sale_id.partner_id.id

        else:
            mp_rec = self.env['mrp.production'].search([
            ('name', '=', self.origin),
        ])
            if mp_rec and mp_rec.sol_id:
                lead_id = mp_rec.lead_id
                owner_id = mp_rec.owner_id
                if mp_rec.sol_id.order_id.opportunity_id:
                    lead_id = mp_rec.sol_id.order_id.opportunity_id.id
                owner_id = mp_rec.sol_id.order_id.partner_id.id
                so_id = mp_rec.sol_id and mp_rec.sol_id.order_id.id
        if lead_id and (not self.lead_w or (self.lead_w and not self.lead_id)):
            self.write({
                'lead_id': lead_id,
            })

        if owner_id and (not self.owner_w or (self.owner_w and not self.owner_id)):
            self.write({
                'owner_id': owner_id,
            })
        self.write({
            'so_id': so_id,
        })
        return False

    so_id = fields.Many2one('sale.order', 'SO', compute="_get_so")
    lead_id = fields.Many2one('crm.lead', 'Komisja')
    owner_v = fields.Boolean(related='picking_type_id.owner', readonly=True, store=False)
    lead_v = fields.Boolean(related='picking_type_id.lead', readonly=True, store=False)
    owner_w = fields.Boolean(related='picking_type_id.owner_w', readonly=True, store=False)
    lead_w = fields.Boolean(related='picking_type_id.lead_w', readonly=True, store=False)
    owner_c = fields.Boolean(related='picking_type_id.owner_c', readonly=True, store=False)
    lead_c = fields.Boolean(related='picking_type_id.lead_c', readonly=True, store=False)

    # @api.one
    def action_assign_lead(self):
        self.move_line_ids.write({'lead_id': self.lead_id.id})

    # @api.multi
    # def button_validate(self):
    #     res= super(Picking,self).button_validate()
    #     return res

    # @api.multi
    def button_validate(self):
        lines_to_check = self.move_line_ids
        if self.picking_type_id.owner_q and not self.owner_id:
            raise UserError('Właściciel wymagany!')
        if self.picking_type_id.lead_q and not self.lead_id:
            raise UserError('Komisja wymagana!')

        if self.owner_c:
            for line in lines_to_check:
                if line.product_id.tracking != 'lot':
                    continue
                if line.owner_id.id != self.owner_id.id:
                    raise UserError('Właściciel niezgodny z zamówieniem')
        if self.lead_c:
            for line in lines_to_check:
                if line.product_id.tracking != 'lot':
                    continue
            if line.lead_id.id != self.lead_id.id:
                raise UserError('Komisja niezgodna z zamówieniem')

        res =  super(Picking, self).button_validate()
        lines_to_check = self.move_line_ids
        for line in lines_to_check:
            line.lot_id._get_pq()

        return res

    # @api.multi
    def action_assign(self):
        if self.picking_type_id.assign_lot:
            location = self.picking_type_id.default_location_src_id.id
            location_obj = self.env['stock.location']
            locs = location_obj.search([('parent_path','ilike',str(location)+'/%')])
            locs_ids = [x.id for x in locs]


            sml_obj = self.env['stock.move.line']
            moves = self.mapped('move_lines').filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))
            for move in moves:
                if move.product_id.tracking == 'serial':
                    super(Picking,self).action_assign()
                    continue
                if move.product_id.tracking =='none':
                    qty_to = move.product_uom_qty
                    for line in move.move_line_ids:
                        qty_to -= line.product_uom_qty
                    if qty_to <=0:
                        move.write({'state':'assigned'})
                        continue

                    owner_id = self.owner_id

                    quants = self.env['stock.quant'].search([
                        ('quantity', '>=', qty_to),
                        ('location_id', 'in', locs_ids),
                        ('product_id', '=', move.product_id.id),
                        ('owner_id','=',owner_id.id)
                    ], order='quantity asc, in_date', limit=1)
                    qty = qty_to
                    if not quants:
                        quants = self.env['stock.quant'].search([
                        ('quantity', '>=', 1),
                        ('location_id', 'in', locs_ids),
                        ('product_id', '=', move.product_id.id),
                        ('owner_id', '=', owner_id.id)
                    ], order='quantity asc, in_date', limit=1)
                        if quants:
                            qty = quants[0].quantity
                    if quants:
                        vals = {'move_id': move.id,
                                'product_id': move.product_id.id,
                                'product_uom_id': move.product_uom.id,
                                'location_id': quants[0].location_id.id,
                                'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                'picking_id': self.id,
                                'product_uom_qty': qty,
                                'owner_id': quants[0].owner_id.id,
                                'lead_id': self.lead_id.id,
                                'state': 'assigned'
                                }
                        sm = sml_obj.create(vals)
                        owner_id_d = quants[0].owner_id
                        self.env['stock.quant']._update_reserved_quantity(
                            move.product_id, quants[0].location_id,  qty, lot_id=False,
                            package_id=False, owner_id=owner_id, strict=True
                        )
                        # move.write({'state': 'assigned'})
                        qty_to -= qty
                    if qty_to >0:
                        quants = self.env['stock.quant'].search([
                            ('quantity', '>=', qty_to),
                            ('location_id', 'in', locs_ids),
                            ('product_id', '=', move.product_id.id),
                            ('owner_id', '=', move.product_id.owner_id.id)
                        ], order='quantity asc, in_date', limit=1)
                        if quants:
                            qty = qty_to
                        else:
                            quants = self.env['stock.quant'].search([
                                ('quantity', '>=', 1),
                                ('location_id', 'in', locs_ids),
                                ('product_id', '=', move.product_id.id),
                                ('owner_id', '=', move.product_id.owner_id.id)
                            ], order='quantity desc, in_date', limit=1)
                            if quants:
                                qty = quants[0].quantity
                        if quants:
                            vals = {'move_id': move.id,
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_uom.id,
                                    'location_id': quants[0].location_id.id,
                                    'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                    'picking_id': self.id,
                                    'product_uom_qty': qty,
                                    'owner_id': quants[0].owner_id.id,
                                    'lead_id': self.lead_id.id,
                                    'state': 'assigned'
                                    }

                            sm = sml_obj.create(vals)
                            owner_id_d = quants[0].owner_id
                            self.env['stock.quant']._update_reserved_quantity(
                                move.product_id, quants[0].location_id, qty, lot_id=False,
                                package_id=False, owner_id=owner_id_d, strict=True
                            )
                            qty_to -= qty
                        if qty_to<=0:
                            move.write({'state': 'assigned'})
                            self.write({'state': 'assigned'})
                            for line in move.move_line_ids:
                                line.write({'state': 'assigned'})
                        else:
                            move.write({'state': 'partially_available'})
                    # super(Picking,self).action_assign()
                    else:
                        move.write({'state': 'assigned'})
                        self.write({'state': 'assigned'})
                    continue
                else:
                    qty_to = move.product_uom_qty
                    boms = []
                    if self.so_id.id:
                        sol = self.env['sale.order.line'].search([
                        # ('product_id', '=',move.product_id.id ),
                        ('order_id', '=', self.so_id.id),
                        ],)
                        boms = [x.bom_id for x in sol]
                    lots_ids = []
                    bom_wqty = {}
                    for y in boms:
                        for x in y.bom_line_ids:
                            if x.product_id.id != move.product_id.id:
                                continue
                            if x.lot_id:
                                lots_ids.append(x.lot_id.id)
                            if x.lot_id.id not in bom_wqty.keys():
                                bom_wqty[x.lot_id.id] = x.product_qty
                    lot_qty_in_bom = len(bom_wqty.keys())
                    if lot_qty_in_bom > 1:
                        for bom_key in bom_wqty.keys():
                            quants = self.env['stock.quant'].search([
                                ('quantity', '>=', bom_wqty[bom_key]),
                                ('lot_id', '=', bom_key),
                                ('location_id', 'in', locs_ids),
                                ('product_id', '=', move.product_id.id),
                            ], order='quantity asc, in_date', limit=1)
                            if not quants:
                                raise UserError('Za mała ilość produktu w wybranym LOT!')
                            else:
                                if move.product_id.lot_reservation_type == '1':
                                    qty = quants[0].quantity
                                else:
                                    qty = bom_wqty[bom_key]

                                vals = {'move_id': move.id,
                                        'product_id': move.product_id.id,
                                        'product_uom_id': move.product_uom.id,
                                        'location_id': quants[0].location_id.id,
                                        'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                        'picking_id': self.id,
                                        'product_uom_qty': qty,
                                        'lot_id': quants[0].lot_id.id,
                                        'owner_id': quants[0].lot_id.owner_id.id,
                                        'lead_id': quants[0].lot_id.lead_id.id,
                                        'state': 'assigned'

                                        }
                                sm = sml_obj.create(vals)
                                owner_id_d = quants[0].lot_id.owner_id
                                self.env['stock.quant']._update_reserved_quantity(
                                    move.product_id, quants[0].location_id, qty, lot_id=quants[0].lot_id,
                                    package_id=False, owner_id=owner_id_d, strict=True
                                )
                        move.write({'state': 'assigned'})
                        continue







                    for line in move.move_line_ids:
                        qty_to -= line.product_uom_qty
                    if qty_to <=0:
                        continue
                    lots = self.env['stock.production.lot'].search(['&','&',('product_id','=',move.product_id.id),('owner_id','=',self.owner_id.id),('lead_id','=',self.lead_id.id)])
                    lot_ids = [x.id for x in lots]
                    if lots_ids or lot_ids:
                        quants_ok = []
                        quants = self.env['stock.quant'].search([
                            ('quantity', '>=', qty_to),
                            ('lot_id', 'in', lots_ids),
                            ('location_id','in',locs_ids),
                            ('product_id', '=', move.product_id.id),
                        ],order='quantity asc, in_date', limit=1)
                        if quants:

                            if move.product_id.lot_reservation_type =='1':
                                qty = quants[0].quantity
                            else:
                                qty = qty_to
                            vals = {'move_id': move.id,
                                'product_id': move.product_id.id,
                                'product_uom_id': move.product_uom.id,
                                'location_id': quants[0].location_id.id,
                                'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                'picking_id': self.id,
                                'product_uom_qty': qty,
                                'lot_id': quants[0].lot_id.id,
                                'owner_id': quants[0].lot_id.owner_id.id,
                                'lead_id': quants[0].lot_id.lead_id.id,
                                'state':'assigned'

                                }
                            sm = sml_obj.create(vals)
                            owner_id_d = quants[0].lot_id.owner_id
                            self.env['stock.quant']._update_reserved_quantity(
                                move.product_id, quants[0].location_id, qty, lot_id=quants[0].lot_id,
                                package_id=False, owner_id=owner_id_d, strict=True
                            )
                            move.write({'state': 'assigned'})
                        else:
                            quants = self.env['stock.quant'].search([
                                ('quantity', '>', 0),
                                ('lot_id', 'in', lots_ids),
                                ('reserved_quantity', '=', 0),
                                ('product_id', '=', move.product_id.id),
                                ('location_id', 'in', locs_ids),
                            ],order='quantity desc')


                            qty = move.product_uom_qty
                            for quant in quants:
                                if move.product_id.lot_reservation_type != '1' and qty < quant.quantity:
                                    qty_1 = qty
                                else:
                                    qty_1 = quant.quantity

                                qty -= qty_1
                                quants_ok.append((quant, qty_1))
                                if qty <=0:
                                    break
                            # if qty < 0:
                            if qty >0:
                                quants = self.env['stock.quant'].search([
                                    ('quantity', '>=', qty),
                                    ('lot_id', 'in', lot_ids),
                                    ('reserved_quantity', '=', 0),
                                    ('product_id', '=', move.product_id.id),
                                    ('location_id', 'in', locs_ids),
                                ], order='quantity desc')
                                if quants:

                                    if move.product_id.lot_reservation_type == '1':
                                        qty_2 = quants[0].quantity
                                    else:
                                        qty_2 = qty
                                    qty-=qty_2
                                    vals = {'move_id': move.id,
                                            'product_id': move.product_id.id,
                                            'product_uom_id': move.product_uom.id,
                                            'location_id': quants[0].location_id.id,
                                            'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                            'picking_id': self.id,
                                            'product_uom_qty': qty_2,
                                            'lot_id': quants[0].lot_id.id,
                                            'owner_id': quants[0].lot_id.owner_id.id,
                                            'lead_id': quants[0].lot_id.lead_id.id,
                                            'state': 'assigned'

                                            }
                                    sm = sml_obj.create(vals)
                                    owner_id_d = quants[0].lot_id.owner_id
                                    self.env['stock.quant']._update_reserved_quantity(
                                        move.product_id, quants[0].location_id, qty_2, lot_id=quants[0].lot_id,
                                        package_id=False, owner_id=owner_id_d, strict=True
                                    )
                                    move.write({'state': 'assigned'})
                                else:
                                    quants = self.env['stock.quant'].search([
                                        ('quantity', '>', 0),
                                        ('lot_id', 'in', lot_ids),
                                        ('reserved_quantity', '=', 0),
                                        ('product_id', '=', move.product_id.id),
                                        ('location_id', 'in', locs_ids),
                                    ], order='quantity desc')
                                    for quant in quants:
                                        if move.product_id.lot_reservation_type != '1' and qty < quant.quantity:
                                            qty_1 = qty
                                        else:
                                            qty_1 = quant.quantity

                                        qty -= qty_1
                                        quants_ok.append((quant,qty_1))
                                        if qty <= 0:
                                            break
                        for quant in quants_ok:
                            vals = {'move_id': move.id,
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_uom.id,
                                    'location_id': quant[0].location_id.id,
                                    'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                    'picking_id': self.id,
                                    'product_uom_qty': quant[1],
                                    'lot_id': quant[0].lot_id.id,
                                    'owner_id': quant[0].lot_id.owner_id.id,
                                    'lead_id': quant[0].lot_id.lead_id.id,
                                    'state': 'assigned'

                                    }
                            sm = sml_obj.create(vals)
                            self.env['stock.quant']._update_reserved_quantity(
                                move.product_id, quant[0].location_id,  quant[1], lot_id=quant[0].lot_id,
                                package_id=False, owner_id=quant[0].lot_id.owner_id, strict=True
                            )
                            move.write({'state': 'partially_available'})
                            if qty <=0:
                                move.write({'state': 'assigned'})
        moves = self.mapped('move_lines').filtered(lambda move: move.state not in ('assigned'))
        if moves:
            self.write({'state':'confirmed'})
            return True
        else:
            self.write({'state': 'assigned'})
            return True





class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.onchange('lot_id')
    def onchange_lot(self):
        if self.lot_id:
            self.lead_id = self.lot_id.lead_id.id
            self.owner_id = self.lot_id.owner_id.id



    owner_v = fields.Boolean(related='picking_id.owner_v', readonly=True, store=False)
    lead_v = fields.Boolean(related='picking_id.lead_v', readonly=True, store=False)
    owner_w = fields.Boolean(related='picking_id.owner_w', readonly=True, store=False)
    lead_w = fields.Boolean(related='picking_id.lead_w', readonly=True, store=False)

    lead_id = fields.Many2one('crm.lead', 'Komisja')

    def write(self, vals):

        vals2 = {}
        meh = self
        if vals.get('lot_id',False):
            lot_rec = self.env['stock.production.lot'].browse(vals.get('lot_id',False))
            if self.picking_id.lead_w:
                vals2['lead_id'] = self.lead_id.id
            else:
                vals2['lead_id'] = lot_rec.lead_id.id

            if self.picking_id.owner_w:
                vals2['owner_id'] = self.owner_id.id
            else:
                vals2['owner_id'] = lot_rec.owner_id.id
        if vals2:
            vals.update(vals2)
            lot_rec.write(vals2)
        if vals.get('owner_id', False):
            ssm = []
            for sml in self:
                if not(sml.owner_id.id != vals.get('owner_id', False) and sml.product_id.tracking=='none'):
                    ssm.append(sml.id)
            meh = self.env['stock.move.line'].browse(ssm)
        res = super(StockMoveLine, meh).write(vals)

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals):
        ctx = dict(self._context)
        owner_id = False
        in_picking = False
        if ctx and isinstance(ctx,dict) and ctx.get('default_picking_type_id',0) == 1:
            in_picking=True
            if ctx.get('default_owner_id',False):
                owner_id = ctx.get('default_owner_id',False)

        if isinstance(vals,list):
            for val in vals:
                if not owner_id and val.get('move_id',False) and in_picking:
                    sm_rec = self.env['stock.move'].browse(val.get('move_id', False))
                    owner_id = sm_rec.owner_id and sm_rec.owner_id.id

                if not val.get('owner_id',False) and owner_id:
                    val['owner_id'] = owner_id
                if val.get('lot_id',False):
                    lot_rec = self.env['stock.production.lot'].browse(val.get('lot_id',False))
                    if not val.get('lead_id',False) and not val.get('owner_id',False):
                        val['lead_id'] = lot_rec.lead_id.id
                        val['owner_id'] = lot_rec.owner_id.id
        if isinstance(vals,dict):
            if not owner_id and vals.get('move_id', False) and in_picking:
                sm_rec = self.env['stock.move'].browse(vals.get('move_id', False))
                owner_id = sm_rec.owner_id and sm_rec.owner_id.id
            if not vals.get('owner_id', False) and owner_id:
                vals['owner_id'] = owner_id
            if vals.get('lot_id', False):
                lot_rec = self.env['stock.production.lot'].browse(vals.get('lot_id', False))
                if not vals.get('lead_id', False) and not vals.get('owner_id', False):
                    vals['lead_id'] = lot_rec.lead_id.id
                    vals['owner_id'] = lot_rec.owner_id.id
        return super(StockMoveLine, self).create(vals)


    @api.onchange('lot_id')
    def onchange_lot_id(self):
        """ Changes UoM if product_id changes. """
        if not self.lead_v:
            self.lead_id = self.lot_id.lead_id.id
        if not self.owner_v:
            self.owner_id = self.lot_id.owner_id.id


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    lead = fields.Boolean( 'Komisja widoczna')
    owner = fields.Boolean('Właściciel widoczny')
    lead_w = fields.Boolean('Komisja możliwa do edycji')
    owner_w = fields.Boolean('Właściciel możliwy do edycji')
    lead_c = fields.Boolean('Komisja dokumentu musi być zgodna na liniach')
    owner_c = fields.Boolean('Właściciel dokumentu musi być zgodny na liniach')
    assign_lot = fields.Boolean('Metoda rezerwacji LOT')
    lead_q = fields.Boolean('Komisja wymagana')
    owner_q = fields.Boolean('Właściciel wymagany')



class StockMove(models.Model):
    _inherit = "stock.move"

    lead_id = fields.Many2one(related='picking_id.lead_id', readonly=True, store=False)
    owner_id = fields.Many2one(related='picking_id.owner_id', readonly=True, store=False)

    def action_show_details(self):
        res = super(StockMove, self).action_show_details()
        if res and res.get('context',False) and self.picking_id.owner_id:
            res['context']['default_owner_id']=self.picking_id.owner_id.id
        if res and res.get('context', False) and self.picking_id.lead_id:
            res['context']['default_lead_id'] = self.picking_id.lead_id.id
        return res



