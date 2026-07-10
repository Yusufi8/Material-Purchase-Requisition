from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TiStockReturnWizard(models.TransientModel):
    """Return previously issued materials to stock, decrementing
    qty_issued on the affected lines. Reachable once a requisition is
    'issued' or 'completed'."""
    _name = 'ti.stock.return.wizard'
    _description = 'Stock Return Wizard'

    RETURN_STATES = ('issued', 'completed')

    mr_id = fields.Many2one('material.requisition', string='Material Requisition',
                             required=True, readonly=True)
    line_ids = fields.One2many('ti.stock.return.wizard.line', 'wizard_id', string='Lines')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mr_id = self.env.context.get('default_mr_id') or self.env.context.get('active_id')
        if mr_id and 'line_ids' in fields_list:
            mr = self.env['material.requisition'].browse(mr_id)
            line_vals = []
            for line in mr.line_ids:
                if (line.qty_issued or 0.0) <= 0:
                    continue
                line_vals.append((0, 0, {
                    'mr_line_id': line.id,
                    'product_id': line.product_id.id,
                    'qty_issued': line.qty_issued,
                    'qty_to_return': 0.0,
                }))
            res['line_ids'] = line_vals
        return res

    def action_create_return(self):
        self.ensure_one()
        mr = self.mr_id
        if mr.state not in self.RETURN_STATES:
            raise UserError(_('Returns can only be created for issued or completed requisitions.'))

        lines_to_process = self.line_ids.filtered(lambda l: (l.qty_to_return or 0.0) > 0)
        if not lines_to_process:
            raise UserError(_('Enter a quantity to return for at least one line.'))
        for wl in lines_to_process:
            if wl.qty_to_return > wl.qty_issued + 0.0001:
                raise UserError(
                    _('Cannot return more than the issued quantity for %s.')
                    % wl.product_id.display_name
                )

        stock_loc = self.env.ref('stock.stock_location_stock')
        prod_loc = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [False, self.env.company.id]),
        ], limit=1)
        if not prod_loc:
            raise UserError(_('Production location not found. Please configure one.'))
        pick_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ], limit=1)
        if not pick_type:
            raise UserError(_('No internal picking type found. Please configure your warehouse.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': pick_type.id,
            'location_id': prod_loc.id,
            'location_dest_id': stock_loc.id,
            'origin': _('Return: %s') % mr.name,
            'note': _('Return to stock from Material Requisition: %s') % mr.name,
        })
        for wl in lines_to_process:
            self.env['stock.move'].create({
                'name': wl.product_id.display_name,
                'product_id': wl.product_id.id,
                'product_uom_qty': wl.qty_to_return,
                'product_uom': wl.mr_line_id.uom_id.id or wl.product_id.uom_id.id,
                'location_id': prod_loc.id,
                'location_dest_id': stock_loc.id,
                'picking_id': picking.id,
                'origin': _('Return: %s') % mr.name,
            })
            wl.mr_line_id.qty_issued = max(
                (wl.mr_line_id.qty_issued or 0.0) - wl.qty_to_return, 0.0
            )

        picking.action_confirm()
        picking.action_assign()

        # Non-state-changing action — still audited. See the identical note
        # in ti.issue.materials.wizard: nothing should change silently, even
        # when the requisition's state itself doesn't move.
        mr._ti_log_transition(_('Process Return'), mr.state, mr.state)
        mr._ti_create_timeline_event(
            'created', _('Materials Returned to Stock'), description=picking.name
        )
        mr.message_post(body=_('Return processed via transfer %s.') % picking.name)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }


class TiStockReturnWizardLine(models.TransientModel):
    _name = 'ti.stock.return.wizard.line'
    _description = 'Stock Return Wizard Line'

    wizard_id = fields.Many2one(
        'ti.stock.return.wizard', required=True, ondelete='cascade',
    )
    mr_line_id = fields.Many2one(
        'material.requisition.line', string='Requisition Line',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    qty_issued = fields.Float(string='Issued', readonly=True)
    qty_to_return = fields.Float(string='Return Qty')
