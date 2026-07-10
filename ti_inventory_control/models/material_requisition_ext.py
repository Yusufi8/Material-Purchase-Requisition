from odoo import api, fields, models


class MaterialRequisitionExtInventory(models.Model):
    """Fulfilment tracking fields for material.requisition.

    All six fields are computed from a single method sharing one set of
    @api.depends, so they update atomically whenever any line's requested,
    approved, or issued quantity changes — including from a partial issue
    or a return processed by the wizards in this module.
    """
    _inherit = 'material.requisition'

    total_requested_qty = fields.Float(
        string='Total Requested', compute='_compute_fulfilment_totals',
        store=True, digits='Product Unit of Measure',
    )
    total_approved_qty = fields.Float(
        string='Total Approved', compute='_compute_fulfilment_totals',
        store=True, digits='Product Unit of Measure',
    )
    total_issued_qty = fields.Float(
        string='Total Issued', compute='_compute_fulfilment_totals',
        store=True, digits='Product Unit of Measure',
    )
    total_pending_qty = fields.Float(
        string='Total Pending', compute='_compute_fulfilment_totals',
        store=True, digits='Product Unit of Measure',
    )
    fulfillment_rate = fields.Float(
        string='Fulfilment Rate (%)', compute='_compute_fulfilment_totals',
        store=True, digits=(5, 2),
        help='Percentage of total requested quantity issued so far, 0-100.',
    )
    is_fully_issued = fields.Boolean(
        string='Fully Issued', compute='_compute_fulfilment_totals', store=True,
    )

    @api.depends('line_ids.qty_requested', 'line_ids.qty_approved', 'line_ids.qty_issued')
    def _compute_fulfilment_totals(self):
        for rec in self:
            total_requested = sum(rec.line_ids.mapped('qty_requested'))
            total_approved = sum(rec.line_ids.mapped('qty_approved'))
            total_issued = sum(rec.line_ids.mapped('qty_issued'))
            rec.total_requested_qty = total_requested
            rec.total_approved_qty = total_approved
            rec.total_issued_qty = total_issued
            rec.total_pending_qty = total_requested - total_issued
            rec.fulfillment_rate = (
                (total_issued / total_requested * 100.0) if total_requested else 0.0
            )
            rec.is_fully_issued = (total_requested - total_issued) <= 0.0001
