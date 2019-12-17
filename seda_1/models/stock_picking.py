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

        return super(Picking, self).button_validate()

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
                if move.product_id.tracking != 'lot':
                    super(Picking,self).action_assign()
                            # move.product_id, move.location_id, move.product_uom_qty, lot_id=False,
                            # package_id=False, owner_id=False, strict=True)
                    # move.write({'state': 'assigned'})
                    continue
                qty_to = move.product_uom_qty
                for line in move.move_line_ids:
                    qty_to -= line.product_uom_qty
                if qty_to <=0:
                    continue
                lots = self.env['stock.production.lot'].search(['&','&',('product_id','=',move.product_id.id),('owner_id','=',self.owner_id.id),('lead_id','=',self.lead_id.id)])
                lot_ids = [x.id for x in lots]
                if lot_ids:
                    quants = self.env['stock.quant'].search([
                        ('quantity', '>=', qty_to),
                        ('lot_id', 'in', lot_ids),
                        ('location_id','in',locs_ids),
                        # ('reserved_quantity','=',0)
                    ],order='quantity asc, in_date', limit=1)
                    if quants:

                        if move.product_id.lot_reservation_type ==1:
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
                        # self.env.cr.execute(
                        #     """update stock_quant set reserved_quantity = %s where id = %s""" % ( quants[0].quantity,  quants[0].id))
                        # quants[0].write({'reserved_quantity':qty})
                        # move.write({'state':'assigned'})
                        self.env['stock.quant']._update_reserved_quantity(
                            move.product_id, quants[0].location_id, qty, lot_id=quants[0].lot_id,
                            package_id=False, owner_id=False, strict=True
                        )
                        # to_unassign = sml_obj.search([
                        # ('lot_id', '=', quants[0].lot_id.id),
                        #     ('product_uom_qty', '>', 0),
                        #     ('qty_done', '=', 0),
                        #     ('move_id','!=',move.id),
                        #     ('picking_id','!=',self.id)
                        #     ])
                        # for to_un in to_unassign:
                        #     to_un.write({   'state': 'confirmed',
                        #                     'product_uom_qty': 0,
                        #                     'lot_id': False
                        #                  })
                        #     to_un.move_id.write({'state':'confirmed'})
                        move.write({'state': 'assigned'})
                    else:
                        quants = self.env['stock.quant'].search([
                            ('quantity', '>', 0),
                            ('lot_id', 'in', lot_ids),
                            ('reserved_quantity', '=', 0),
                            ('location_id', 'in', locs_ids),
                        ],order='quantity desc')
                        quants_ok = []
                        qty = move.product_uom_qty
                        for quant in quants:
                            qty -= quant.quantity
                            quants_ok.append(quant)
                            if qty <0:
                                break
                        # if qty < 0:
                        for quant in quants_ok:
                            vals = {'move_id': move.id,
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_uom.id,
                                    'location_id': quant.location_id.id,
                                    'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                                    'picking_id': self.id,
                                    'product_uom_qty': quant.quantity,
                                    'lot_id': quant.lot_id.id,
                                    'owner_id': quant.lot_id.owner_id.id,
                                    'lead_id': quant.lot_id.lead_id.id,
                                    'state': 'assigned'

                                    }
                            sm = sml_obj.create(vals)
                            self.env['stock.quant']._update_reserved_quantity(
                                move.product_id, quant.location_id,  quant.quantity, lot_id=quant.lot_id,
                                package_id=False, owner_id=quant.lot_id.owner_id, strict=True
                            )

                                # to_unassign = sml_obj.search([
                                #     ('lot_id', '=', quant.lot_id.id),
                                #     ('product_uom_qty', '>', 0),
                                #     ('qty_done', '=', 0),
                                #     ('move_id','!=',move.id),
                                #     ('picking_id','!=',self.id)
                                # ])
                                # for to_un in to_unassign:
                                #     to_un.write({'state': 'confirmed',
                                #                  'product_uom_qty': 0,
                                #                  'lot_id': False
                                #                  })
                                #     to_un.move_id.write({'state': 'confirmed'})
                                # self.env.cr.execute("""update stock_quant set reserved_quantity = %s where id = %s"""%(quant.quantity,quant.id))
                                # quant.write({'reserved_quantity':quant.quantity})

                        # else:
                        #     raise UserError("Brak możliwości rezerwacji - za mało materiału!")
                        move.write({'state': 'partially_available'})
        moves = self.mapped('move_lines').filtered(lambda move: move.state not in ('available'))
        if moves:
            self.write({'state':'confirmed'})
            return True
        else:
            self.write({'state': 'assigned'})
            return super(Picking, self).action_assign()





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
        if vals.get('lot_id',False):
            lot_rec = self.env['stock.production.lot'].browse(vals.get('lot_id',False))
            if self.picking_id.lead_w:
                vals2['lead_id'] = self.lead_id.id
            else:
                vals2['lead_id'] = lot_rec.lead_id.id

        if vals.get('lot_id', False):
            if self.picking_id.owner_w:
                vals2['owner_id'] = self.owner_id.id
            else:
                vals2['owner_id'] = lot_rec.owner_id.id
        if vals2:
            vals.update(vals2)
            lot_rec.write(vals2)
        res = super(StockMoveLine, self).write(vals)

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals):
        if isinstance(vals,list):
            for val in vals:
                if val.get('lot_id',False):
                    lot_rec = self.env['stock.production.lot'].browse(val.get('lot_id',False))
                    if not val.get('lead_id',False) and not val.get('owner_id',False):
                        val['lead_id'] = lot_rec.lead_id.id
                        val['owner_id'] = lot_rec.owner_id.id
        if isinstance(vals,dict):
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



