from odoo import api, fields, models


class MaterialRequisitionLine(models.Model):
    _name = 'material.requisition.line'
    _description = 'Material Requisition Line'

    requisition_id = fields.Many2one(
        'material.requisition',
        string='Material Requisition',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    description = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

    qty_requested = fields.Float(string='Requested Qty', required=True, default=1.0)
    qty_available = fields.Float(
        string='Available (On Hand)',
        compute='_compute_availability',
        store=True,
        digits='Product Unit of Measure',
    )
    qty_approved = fields.Float(string='Approved Qty', digits='Product Unit of Measure')
    qty_issued = fields.Float(string='Issued Qty', readonly=True, digits='Product Unit of Measure')
    shortage_qty = fields.Float(
        string='Shortage',
        compute='_compute_availability',
        store=True,
        digits='Product Unit of Measure',
    )

    state = fields.Selection(related='requisition_id.state', store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.uom_id = self.product_id.uom_id

    @api.depends('product_id', 'qty_requested')
    def _compute_availability(self):
        for line in self:
            if line.product_id:
                available = line.product_id.qty_available
                line.qty_available = available
                line.shortage_qty = max(line.qty_requested - available, 0.0)
            else:
                line.qty_available = 0.0
                line.shortage_qty = 0.0