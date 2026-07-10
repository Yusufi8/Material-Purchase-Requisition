from odoo import api, fields, models


class PurchaseRequisitionRequestLine(models.Model):
    _name = 'purchase.requisition.request.line'
    _description = 'Purchase Requisition Line'
    _order = 'sequence, id'

    requisition_id = fields.Many2one(
        'purchase.requisition.request', string='Purchase Requisition',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

    requested_qty = fields.Float(string='Required Qty', required=True, default=1.0)
    available_qty = fields.Float(string='Available (On Hand)')
    shortage_qty = fields.Float(string='Shortage Qty')

    estimated_cost = fields.Float(
        string='Est. Unit Cost', compute='_compute_estimated_cost',
        store=True, digits='Product Price',
    )
    total_cost = fields.Float(
        string='Est. Total', compute='_compute_estimated_cost',
        store=True, digits='Product Price',
    )
    actual_cost = fields.Float(
        string='Actual Cost', digits='Product Price',
        help='Optional manual reconciliation against the confirmed PO line price. '
             'Automatic PO-line matching is added by ti_procurement.',
    )
    remarks = fields.Char(string='Remarks')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            available = self.product_id.qty_available
            self.available_qty = available
            self.shortage_qty = max(self.requested_qty - available, 0.0)

    @api.onchange('requested_qty')
    def _onchange_requested_qty(self):
        if self.product_id:
            available = self.available_qty or self.product_id.qty_available
            self.shortage_qty = max(self.requested_qty - available, 0.0)

    @api.depends('product_id', 'requested_qty', 'shortage_qty')
    def _compute_estimated_cost(self):
        for line in self:
            line.estimated_cost = line.product_id.standard_price if line.product_id else 0.0
            qty = line.shortage_qty or line.requested_qty
            line.total_cost = line.estimated_cost * qty
