from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TiInventoryReviewWizard(models.TransientModel):
    """Manual alternative to the one-click 'Check Availability' button.

    action_check_availability() on material.requisition auto-approves the
    minimum of requested/on-hand for every line — the fast path. This
    wizard gives the Inventory Manager a deliberate, line-by-line review
    step where they can see system on-hand stock but override the approved
    quantity themselves (e.g. to hold back stock already earmarked for a
    higher-priority requisition). Both paths funnel into the SAME
    material.requisition._finalize_availability_check() so the shortage
    detection, state transition, audit log, timeline, and notification
    behaviour is identical either way — no duplicated workflow logic.
    """
    _name = 'ti.inventory.review.wizard'
    _description = 'Inventory Review Wizard'

    mr_id = fields.Many2one('material.requisition', string='Material Requisition',
                             required=True, readonly=True)
    line_ids = fields.One2many('ti.inventory.review.wizard.line', 'wizard_id', string='Lines')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mr_id = self.env.context.get('default_mr_id') or self.env.context.get('active_id')
        if mr_id and 'line_ids' in fields_list:
            mr = self.env['material.requisition'].browse(mr_id)
            line_vals = []
            for line in mr.line_ids:
                available = line.product_id.qty_available
                line_vals.append((0, 0, {
                    'mr_line_id': line.id,
                    'product_id': line.product_id.id,
                    'qty_requested': line.qty_requested,
                    'qty_available': available,
                    'qty_approved': min(line.qty_requested, available),
                }))
            res['line_ids'] = line_vals
        return res

    def action_confirm_review(self):
        self.ensure_one()
        if self.mr_id.state not in self.mr_id._get_availability_check_states():
            raise UserError(
                _('This requisition is not currently open for inventory review.')
            )
        for wl in self.line_ids:
            wl.mr_line_id.write({
                'qty_available': wl.qty_available,
                'qty_approved': wl.qty_approved,
            })
        self.mr_id._finalize_availability_check()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requisition'),
            'res_model': 'material.requisition',
            'res_id': self.mr_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class TiInventoryReviewWizardLine(models.TransientModel):
    _name = 'ti.inventory.review.wizard.line'
    _description = 'Inventory Review Wizard Line'

    wizard_id = fields.Many2one(
        'ti.inventory.review.wizard', required=True, ondelete='cascade',
    )
    mr_line_id = fields.Many2one(
        'material.requisition.line', string='Requisition Line',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    qty_requested = fields.Float(string='Requested', readonly=True)
    qty_available = fields.Float(string='System On-Hand', readonly=True)
    qty_approved = fields.Float(string='Approve Qty')
