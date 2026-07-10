from odoo import api, fields, models


class MaterialRequisitionLine(models.Model):
    _name = 'material.requisition.line'
    _description = 'Material Requisition Line'
    _order = 'sequence, id'

    requisition_id = fields.Many2one(
        'material.requisition', string='Material Requisition',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

    qty_requested = fields.Float(string='Requested Qty', required=True, default=1.0)
    qty_available = fields.Float(
        string='Available (On Hand)', compute='_compute_availability',
        store=True, digits='Product Unit of Measure',
    )
    qty_approved = fields.Float(string='Approved Qty', digits='Product Unit of Measure')
    qty_reserved = fields.Float(string='Reserved Qty', digits='Product Unit of Measure')
    qty_issued = fields.Float(string='Issued Qty', readonly=True, digits='Product Unit of Measure')
    qty_pending = fields.Float(
        string='Pending Qty', compute='_compute_pending',
        store=True, digits='Product Unit of Measure',
    )
    shortage_qty = fields.Float(
        string='Shortage', compute='_compute_availability',
        store=True, digits='Product Unit of Measure',
    )
    estimated_cost = fields.Float(
        string='Est. Cost', compute='_compute_estimated_cost',
        store=True, digits='Product Price',
        help='Requested quantity valued at the product standard cost.',
    )
    fulfillment_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Fulfilled'),
        ('full', 'Fully Fulfilled'),
    ], string='Fulfillment', compute='_compute_fulfillment_status', store=True)

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

    @api.depends('qty_requested', 'qty_issued')
    def _compute_pending(self):
        for line in self:
            line.qty_pending = line.qty_requested - line.qty_issued

    @api.depends('product_id', 'qty_requested')
    def _compute_estimated_cost(self):
        for line in self:
            line.estimated_cost = (line.product_id.standard_price or 0.0) * (line.qty_requested or 0.0)

    @api.depends('qty_requested', 'qty_issued')
    def _compute_fulfillment_status(self):
        for line in self:
            if (line.qty_issued or 0.0) <= 0:
                line.fulfillment_status = 'pending'
            elif line.qty_issued < line.qty_requested:
                line.fulfillment_status = 'partial'
            else:
                line.fulfillment_status = 'full'
