from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TiIssueMaterialsWizard(models.TransientModel):
    """Issue a partial quantity per line rather than the full approved
    amount in one shot (that full-quantity path is
    material.requisition.action_issue_materials(), already implemented
    directly in ti_material_requisition — this wizard is the alternative
    for splitting an issue across more than one transfer).

    Deliberately does NOT share a precondition hook with
    action_issue_materials(): this is new functionality operating on a
    different granularity (per-line partial quantity, possibly run more
    than once), not an override of an existing method, so there is no
    business logic being duplicated by also checking the same three
    states here.
    """
    _name = 'ti.issue.materials.wizard'
    _description = 'Issue Materials (Partial) Wizard'

    ISSUE_STATES = ('ready_to_issue', 'stock_reserved', 'director_approved')

    mr_id = fields.Many2one('material.requisition', string='Material Requisition',
                             required=True, readonly=True)
    line_ids = fields.One2many('ti.issue.materials.wizard.line', 'wizard_id', string='Lines')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mr_id = self.env.context.get('default_mr_id') or self.env.context.get('active_id')
        if mr_id and 'line_ids' in fields_list:
            mr = self.env['material.requisition'].browse(mr_id)
            line_vals = []
            for line in mr.line_ids:
                remaining = (line.qty_approved or 0.0) - (line.qty_issued or 0.0)
                if remaining <= 0.0001:
                    continue
                line_vals.append((0, 0, {
                    'mr_line_id': line.id,
                    'product_id': line.product_id.id,
                    'qty_approved': line.qty_approved,
                    'qty_already_issued': line.qty_issued,
                    'qty_remaining': remaining,
                    'qty_to_issue': remaining,
                }))
            res['line_ids'] = line_vals
        return res

    def action_issue_partial(self):
        self.ensure_one()
        mr = self.mr_id
        if mr.state not in self.ISSUE_STATES:
            raise UserError(_('Materials can only be issued once the requisition is ready.'))

        lines_to_process = self.line_ids.filtered(lambda l: (l.qty_to_issue or 0.0) > 0)
        if not lines_to_process:
            raise UserError(_('Enter a quantity to issue for at least one line.'))
        for wl in lines_to_process:
            if wl.qty_to_issue > wl.qty_remaining + 0.0001:
                raise UserError(
                    _('Cannot issue more than the remaining approved quantity for %s.')
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
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'origin': mr.name,
            'note': _('Partial issue from Material Requisition: %s') % mr.name,
        })
        for wl in lines_to_process:
            self.env['stock.move'].create({
                'name': wl.product_id.display_name,
                'product_id': wl.product_id.id,
                'product_uom_qty': wl.qty_to_issue,
                'product_uom': wl.mr_line_id.uom_id.id or wl.product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'picking_id': picking.id,
                'origin': mr.name,
            })
            wl.mr_line_id.qty_issued = (wl.mr_line_id.qty_issued or 0.0) + wl.qty_to_issue

        picking.action_confirm()
        picking.action_assign()

        # Direct tally on freshly-written child records, rather than trusting
        # mr.is_fully_issued's stored-compute recompute timing within this
        # same transaction.
        total_requested = sum(mr.line_ids.mapped('qty_requested'))
        total_issued = sum(mr.line_ids.mapped('qty_issued'))
        fully_issued = (total_requested - total_issued) <= 0.0001

        old_state = mr.state
        if fully_issued and mr.state != 'issued':
            mr.write({'state': 'issued'})
            mr._ti_log_transition(_('Partial Issue (Completed)'), old_state, 'issued')
            mr._ti_create_timeline_event(
                'issued', _('Materials Fully Issued (via partial runs)'), description=picking.name
            )
            mr._ti_trigger_notifications('issued')
        else:
            # State doesn't change yet — more partial issues may follow.
            # Still logged: nothing should change silently, even non-terminal actions.
            mr._ti_log_transition(_('Partial Issue'), old_state, old_state)
            mr._ti_create_timeline_event(
                'issued', _('Partial Materials Issued'), description=picking.name
            )
        mr.message_post(body=_('Partial materials issued via transfer %s.') % picking.name)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }


class TiIssueMaterialsWizardLine(models.TransientModel):
    _name = 'ti.issue.materials.wizard.line'
    _description = 'Issue Materials (Partial) Wizard Line'

    wizard_id = fields.Many2one(
        'ti.issue.materials.wizard', required=True, ondelete='cascade',
    )
    mr_line_id = fields.Many2one(
        'material.requisition.line', string='Requisition Line',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    qty_approved = fields.Float(string='Approved', readonly=True)
    qty_already_issued = fields.Float(string='Already Issued', readonly=True)
    qty_remaining = fields.Float(string='Remaining', readonly=True)
    qty_to_issue = fields.Float(string='Issue Now')
