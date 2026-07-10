from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MaterialRequisitionExt(models.Model):
    """Extends material.requisition (from ti_material_requisition) to add
    the Purchase Requisition creation step and the state-reopening hook.

    This lives HERE, not in ti_material_requisition, because MR must not
    have a hidden runtime dependency on the purchase.requisition.request
    model — see the note in ti_material_requisition/__manifest__.py and
    README.md. ti_purchase_requisition depends on ti_material_requisition,
    so the extension flows in the correct direction.
    """
    _inherit = 'material.requisition'

    purchase_requisition_ids = fields.One2many(
        'purchase.requisition.request', 'material_requisition_id',
        string='Purchase Requisitions',
    )
    purchase_requisition_count = fields.Integer(
        string='Purchase Requisitions', compute='_compute_purchase_requisition_count',
    )

    def _compute_purchase_requisition_count(self):
        for rec in self:
            rec.purchase_requisition_count = len(rec.purchase_requisition_ids)

    def _get_availability_check_states(self):
        """Extend the base set (inventory_review, director_approved) so
        Inventory can re-run availability once a linked Purchase
        Requisition's shortage has been received — see
        ti_material_requisition/README.md, Extension Point 4."""
        states = super()._get_availability_check_states()
        return tuple(set(states) | {'purchase_requisition_created'})

    def action_create_purchase_requisition(self):
        """Create a Purchase Requisition for all lines with shortages.

        Only reachable once a Director has approved the shortage escalation
        (state == 'director_approved') — see the MR state machine in
        ti_material_requisition/README.md.
        """
        self.ensure_one()
        if self.state != 'director_approved':
            raise UserError(
                _('Purchase Requisition can only be created after Director approval.')
            )
        shortage_lines = self.line_ids.filtered(lambda l: l.shortage_qty > 0)
        if not shortage_lines:
            raise UserError(_('No shortage found. All items are available in stock.'))

        # sudo(): creating a PR here is a controlled consequence of the
        # already-completed director approval workflow step, not a raw
        # user-initiated create against the Purchase Requisitions menu.
        # Without sudo(), a user who also belongs to group_purchase_user
        # (whose own visibility rule intentionally excludes draft PRs) would
        # be blocked from creating the very draft record that rule is
        # meant to hide from them later - a visibility rule should never
        # gate the initial creation of a system-triggered record.
        pr = self.env['purchase.requisition.request'].sudo().create({
            'material_requisition_id': self.id,
            'department_id': self.department_id.id,
            'requested_by': self.requested_by.id,
            'required_date': self.required_date,
        })
        pr._ti_propagate_traceability(self)

        for line in shortage_lines:
            self.env['purchase.requisition.request.line'].sudo().create({
                'requisition_id': pr.id,
                'product_id': line.product_id.id,
                'requested_qty': line.shortage_qty,
                'available_qty': line.qty_available,
                'shortage_qty': line.shortage_qty,
                'remarks': line.description or '',
            })

        old_state = self.state
        self.write({'state': 'purchase_requisition_created'})
        self._ti_log_transition(
            _('Create Purchase Requisition'), old_state, 'purchase_requisition_created'
        )
        self._ti_create_timeline_event(
            'created', _('Purchase Requisition Created'), description=pr.name
        )
        self._ti_trigger_notifications('purchase_requisition_created')
        self.message_post(
            body=_('Purchase Requisition %s created for shortage items.') % pr.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requisition'),
            'res_model': 'purchase.requisition.request',
            'view_mode': 'form',
            'res_id': pr.id,
            'target': 'current',
        }

    def action_view_purchase_requisitions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requisitions'),
            'res_model': 'purchase.requisition.request',
            'view_mode': 'tree,form',
            'domain': [('material_requisition_id', '=', self.id)],
            'target': 'current',
        }
