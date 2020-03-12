# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name' : 'SeDa-1',
    'depends' : ['stock',
                 'sale_crm',
                 'sale',
                 'mrp'
                 ],
    #'description': < auto-loaded from README file
    'category' : 'Extra Tools',
    'data' : [
        'views/stock_picking.xml',
        'views/stock_production_lot.xml',
        'views/sale_order.xml',
        'views/product_product.xml',
        'views/mrp_production.xml',
        'views/quants.xml',
        # 'security/ir.model.access.csv'
    ],
}
