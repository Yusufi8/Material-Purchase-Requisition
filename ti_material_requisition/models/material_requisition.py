from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MaterialRequisition(models.Model):
    """Material Requisition.

    Production Supervisor requests materials → Supervisor approves →
    Inventory reviews and checks availability → if a shortage is found,
    a Director approves the escalation → materials are issued.

    This model stops at 'director_approved' on the shortage path. The
    'purchase_requisition_created' state exists in the selection for
    display/statusbar continuity, but no method in THIS module transitions
    into it — that is added by ti_purchase_requisition via _inherit, once
    that module (which depends on this one) is installed. See the note in
    __manifest__.py.
    """
    _name = 'material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ti.workflow.mixin']
    _order = 'date desc, id desc'

    # ------------------------------------------------------------------
    # General Information
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Requisition No', required=True, copy=False,
        readonly=True, default='New', tracking=True,
    )
    date = fields.Date(string='Date', default=fields.Date.today, required=True, tracking=True)
    required_date = fields.Date(string='Required By', tracking=True)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Critical'),
    ], string='Priority', default='0', tracking=True)
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True, tracking=True,
    )
    prepared_by = fields.Many2one(
        'res.users', string='Prepared By',
        default=lambda self: self.env.user, required=True, readonly=True, tracking=True,
        help='Who actually created this requisition record. Always set at creation '
             'and never editable afterward, so it stays a reliable audit reference '
             'even if Requested By is later reassigned to represent a different '
             'department contact.',
    )
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    supervisor_id = fields.Many2one('res.users', string='Approved By (Supervisor)', tracking=True)
    remarks = fields.Text(string='Purpose / Remarks')

    # Business References (sale_order_id, project_id, manufacturing_order_id,
    # work_order_id, cost_center_id) are inherited from ti.workflow.mixin —
    # deliberately NOT redeclared here.

    # ------------------------------------------------------------------
    # State Machine
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('supervisor_approved', 'Supervisor Approved'),
        ('inventory_review', 'Inventory Review'),
        ('stock_reserved', 'Stock Reserved'),
        ('partially_available', 'Partially Available'),
        ('ready_to_issue', 'Ready to Issue'),
        ('director_approval_required', 'Director Approval Required'),
        ('director_approved', 'Director Approved'),
        ('purchase_requisition_created', 'PR Created'),
        ('issued', 'Issued'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ------------------------------------------------------------------
    # Approval Information
    # ------------------------------------------------------------------
    submitted_by = fields.Many2one('res.users', string='Submitted By', readonly=True)
    submitted_date = fields.Datetime(string='Submitted Date', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_date = fields.Datetime(string='Approved Date', readonly=True)
    inventory_manager_id = fields.Many2one('res.users', string='Inventory Manager', readonly=True)
    inventory_review_date = fields.Datetime(string='Inventory Review Date', readonly=True)

    # ------------------------------------------------------------------
    # Director Information
    # ------------------------------------------------------------------
    director_approval_required = fields.Boolean(
        string='Director Approval Required',
        compute='_compute_director_approval_required', store=True,
    )
    director_approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Director Approval Status', default='pending', tracking=True)
    director_approved_by = fields.Many2one('res.users', string='Director Approved By', readonly=True)
    director_approved_date = fields.Datetime(string='Director Approved Date', readonly=True)
    director_remarks = fields.Text(string='Director Remarks')

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    line_ids = fields.One2many('material.requisition.line', 'requisition_id', string='Requested Items')

    # ------------------------------------------------------------------
    # Smart Button Counts
    # ------------------------------------------------------------------
    stock_picking_count = fields.Integer(string='Transfers', compute='_compute_stock_picking_count')
    audit_log_count = fields.Integer(string='Audit Log', compute='_compute_ti_counts')
    timeline_count = fields.Integer(string='Timeline', compute='_compute_ti_counts')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Requisition number must be unique.'),
    ]

    # ------------------------------------------------------------------
    # ORM Overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('material.requisition') or 'New'
                )
        records = super().create(vals_list)
        for rec in records:
            rec._ti_create_timeline_event('created', _('Material Requisition Created'))
        return records

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(
                    _('You can only delete requisitions in Draft or Cancelled state.')
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # Computed Fields
    # ------------------------------------------------------------------
    @api.depends('line_ids.shortage_qty')
    def _compute_director_approval_required(self):
        for rec in self:
            rec.director_approval_required = any(
                (line.shortage_qty or 0.0) > 0 for line in rec.line_ids
            )

    def _compute_stock_picking_count(self):
        for rec in self:
            rec.stock_picking_count = self.env['stock.picking'].search_count([
                ('origin', '=', rec.name),
            ])

    def _compute_ti_counts(self):
        Log = self.env['ti.workflow.log'].sudo()
        Timeline = self.env['ti.document.timeline'].sudo()
        for rec in self:
            rec.audit_log_count = Log.search_count([
                ('document_model', '=', rec._name), ('document_id', '=', rec.id),
            ])
            rec.timeline_count = Timeline.search_count([
                ('document_model', '=', rec._name), ('document_id', '=', rec.id),
            ])

    # ------------------------------------------------------------------
    # Workflow Actions
    # ------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requisitions can be submitted.'))
            if not rec.line_ids:
                raise UserError(_('Please add at least one product before submitting.'))
            old_state = rec.state
            rec.write({
                'state': 'submitted',
                'submitted_by': self.env.uid,
                'submitted_date': fields.Datetime.now(),
            })
            rec._ti_log_transition(_('Submit'), old_state, 'submitted')
            rec._ti_create_timeline_event('submitted', _('Submitted for Supervisor Approval'))
            rec._ti_trigger_notifications('submitted')
            rec.message_post(
                body=_('Material Requisition submitted by %s.') % rec.requested_by.name
            )

    def action_supervisor_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requisitions can be supervisor-approved.'))
            old_state = rec.state
            rec.write({
                'state': 'supervisor_approved',
                'approved_by': self.env.uid,
                'approved_date': fields.Datetime.now(),
                'supervisor_id': self.env.uid,
            })
            rec._ti_log_transition(_('Supervisor Approve'), old_state, 'supervisor_approved')
            rec._ti_create_timeline_event('approved', _('Approved by Supervisor'))
            rec._ti_trigger_notifications('supervisor_approved')
            rec.message_post(
                body=_('Requisition approved by supervisor %s.') % self.env.user.name
            )

    def action_set_inventory_review(self):
        for rec in self:
            if rec.state != 'supervisor_approved':
                raise UserError(
                    _('Only supervisor-approved requisitions can enter inventory review.')
                )
            old_state = rec.state
            rec.write({
                'state': 'inventory_review',
                'inventory_manager_id': self.env.uid,
                'inventory_review_date': fields.Datetime.now(),
            })
            rec._ti_log_transition(_('Start Inventory Review'), old_state, 'inventory_review')
            rec._ti_create_timeline_event('created', _('Inventory Review Started'))
            rec._ti_trigger_notifications('inventory_review')
            rec.message_post(
                body=_('Requisition under inventory review by %s.') % self.env.user.name
            )

    def _get_availability_check_states(self):
        """States from which action_check_availability() (and the Inventory
        Review Wizard) may run. Kept as an overridable hook — rather than a
        hardcoded tuple — so that ti_purchase_requisition can extend this
        list to also allow re-checking once a Purchase Requisition's
        shortage has been procured and received, without needing to
        override or duplicate action_check_availability() or
        _finalize_availability_check() themselves.
        """
        return ('inventory_review', 'director_approved')

    def action_check_availability(self):
        """Fast path: auto-set qty_approved from live stock, then finalize."""
        for rec in self:
            if rec.state not in rec._get_availability_check_states():
                raise UserError(_('Availability can only be checked during inventory review.'))
            if not rec.line_ids:
                raise UserError(_('No items to check.'))
            for line in rec.line_ids:
                available = line.product_id.qty_available
                line.qty_available = available
                line.qty_approved = min(line.qty_requested, available)
            rec._finalize_availability_check()

    def _finalize_availability_check(self):
        """Shared finalization step: determines shortage from the CURRENT
        qty_approved values on the lines and transitions state accordingly.

        Called by action_check_availability() after auto-setting qty_approved
        from live stock, and by the Inventory Review Wizard
        (ti.inventory.review.wizard) after the Inventory Manager has manually
        reviewed and possibly overridden qty_approved per line (e.g. to hold
        back stock reserved for a higher-priority requisition). Kept as one
        method so both paths share identical logging/timeline/notification
        behaviour rather than duplicating it.
        """
        self.ensure_one()
        old_state = self.state
        shortage_found = any(
            (line.qty_requested - (line.qty_approved or 0.0)) > 0.0001
            for line in self.line_ids
        )
        new_state = 'partially_available' if shortage_found else 'ready_to_issue'
        self.write({'state': new_state})
        self._ti_log_transition(_('Check Availability'), old_state, new_state)
        self._ti_create_timeline_event(
            'escalated' if shortage_found else 'approved',
            _('Shortage Found') if shortage_found else _('All Items Available'),
        )
        self._ti_trigger_notifications(new_state)
        self.message_post(
            body=_('Availability checked. Status: %s') % dict(
                self._fields['state'].selection
            ).get(new_state)
        )

    def action_reserve_stock(self):
        for rec in self:
            if rec.state != 'ready_to_issue':
                raise UserError(
                    _('Stock can only be reserved when the requisition is ready to issue.')
                )
            stock_location = self.env.ref('stock.stock_location_stock')
            old_state = rec.state
            Quant = self.env['stock.quant']
            for line in rec.line_ids.filtered(lambda l: (l.qty_approved or 0) > 0):
                Quant._update_reserved_quantity(
                    line.product_id, stock_location, line.qty_approved, strict=False,
                )
                line.qty_reserved = line.qty_approved
            rec.write({'state': 'stock_reserved'})
            rec._ti_log_transition(_('Reserve Stock'), old_state, 'stock_reserved')
            rec._ti_create_timeline_event('approved', _('Stock Reserved'))
            rec._ti_trigger_notifications('stock_reserved')
            rec.message_post(body=_('Stock reserved for issue.'))

    def action_request_director_approval(self):
        for rec in self:
            if rec.state != 'partially_available':
                raise UserError(
                    _('Director approval can only be requested when a shortage has been found.')
                )
            old_state = rec.state
            rec.write({
                'state': 'director_approval_required',
                'director_approval_status': 'pending',
            })
            rec._ti_log_transition(
                _('Request Director Approval'), old_state, 'director_approval_required'
            )
            rec._ti_create_timeline_event('escalated', _('Escalated to Director for Approval'))
            rec._ti_trigger_notifications('director_approval_required')
            rec.message_post(body=_('Shortage escalated to Director for approval.'))

    def action_director_approve(self, remarks=False):
        for rec in self:
            if rec.state != 'director_approval_required':
                raise UserError(
                    _('Only requisitions awaiting director approval can be approved.')
                )
            if not rec._ti_user_can_approve('director_approval_required', 'director_approved'):
                raise UserError(
                    _('You are not authorised to approve this requisition. '
                      'Only Operations Director or Managing Director may approve.')
                )
            old_state = rec.state
            rec.write({
                'state': 'director_approved',
                'director_approval_status': 'approved',
                'director_approved_by': self.env.uid,
                'director_approved_date': fields.Datetime.now(),
                'director_remarks': remarks or rec.director_remarks,
            })
            rec._ti_log_transition(
                _('Director Approve'), old_state, 'director_approved', remarks=remarks or ''
            )
            rec._ti_create_timeline_event('approved', _('Approved by Director'))
            rec._ti_trigger_notifications('director_approved')
            rec.message_post(
                body=_('Shortage approved by Director %s.') % self.env.user.name
            )

    def action_director_reject(self, remarks=False):
        for rec in self:
            if rec.state != 'director_approval_required':
                raise UserError(
                    _('Only requisitions awaiting director approval can be rejected.')
                )
            if not rec._ti_user_can_approve('director_approval_required', 'director_approved'):
                raise UserError(_('You are not authorised to reject this requisition.'))
            old_state = rec.state
            rec.write({
                'state': 'inventory_review',
                'director_approval_status': 'rejected',
                'director_remarks': remarks or rec.director_remarks,
            })
            rec._ti_log_transition(
                _('Director Reject'), old_state, 'inventory_review', remarks=remarks or ''
            )
            rec._ti_create_timeline_event('rejected', _('Rejected by Director — returned for review'))
            rec._ti_trigger_notifications('director_rejected')
            rec.message_post(
                body=_('Shortage rejected by Director %s. Returned for inventory review.')
                % self.env.user.name
            )

    def action_issue_materials(self):
        """Create an internal stock transfer and move approved quantities to production."""
        self.ensure_one()
        if self.state not in ('ready_to_issue', 'stock_reserved', 'director_approved'):
            raise UserError(_('Materials can only be issued once the requisition is ready.'))

        approved_lines = self.line_ids.filtered(lambda l: (l.qty_approved or 0) > 0)
        if not approved_lines:
            raise UserError(_('No approved quantity to issue. Run "Check Availability" first.'))

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

        old_state = self.state
        picking = self.env['stock.picking'].create({
            'picking_type_id': pick_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'origin': self.name,
            'note': _('Issued from Material Requisition: %s') % self.name,
        })

        for line in approved_lines:
            self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty_approved,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'picking_id': picking.id,
                'origin': self.name,
            })
            line.qty_issued = line.qty_approved

        picking.action_confirm()
        picking.action_assign()

        self.write({'state': 'issued'})
        self._ti_log_transition(_('Issue Materials'), old_state, 'issued')
        self._ti_create_timeline_event('issued', _('Materials Issued'), description=picking.name)
        self._ti_trigger_notifications('issued')
        self.message_post(
            body=_('Materials issued via transfer %s.') % picking.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mark_completed(self):
        for rec in self:
            if rec.state != 'issued':
                raise UserError(_('Only issued requisitions can be marked completed.'))
            old_state = rec.state
            rec.write({'state': 'completed'})
            rec._ti_log_transition(_('Mark Completed'), old_state, 'completed')
            rec._ti_create_timeline_event('completed', _('Requisition Completed'))
            rec._ti_trigger_notifications('completed')
            rec.message_post(body=_('Requisition marked as Completed.'))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('completed', 'cancelled'):
                raise UserError(_('This requisition cannot be cancelled.'))
            old_state = rec.state
            rec.write({'state': 'cancelled'})
            rec._ti_log_transition(_('Cancel'), old_state, 'cancelled')
            rec._ti_create_timeline_event('cancelled', _('Requisition Cancelled'))
            rec._ti_trigger_notifications('cancelled')
            rec.message_post(body=_('Requisition cancelled by %s.') % self.env.user.name)

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled requisitions can be reset to draft.'))
            old_state = rec.state
            rec.write({'state': 'draft'})
            rec._ti_log_transition(_('Reset to Draft'), old_state, 'draft')
            rec._ti_create_timeline_event('created', _('Reset to Draft'))
            rec.message_post(body=_('Requisition reset to draft by %s.') % self.env.user.name)

    # ------------------------------------------------------------------
    # Smart Button Actions
    # ------------------------------------------------------------------
    def action_view_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('origin', '=', self.name)],
            'target': 'current',
        }

    def action_view_audit_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Audit Log'),
            'res_model': 'ti.workflow.log',
            'view_mode': 'tree,form',
            'domain': [('document_model', '=', self._name), ('document_id', '=', self.id)],
            'target': 'current',
        }

    def action_view_timeline(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timeline'),
            'res_model': 'ti.document.timeline',
            'view_mode': 'tree,form',
            'domain': [('document_model', '=', self._name), ('document_id', '=', self.id)],
            'target': 'current',
        }
