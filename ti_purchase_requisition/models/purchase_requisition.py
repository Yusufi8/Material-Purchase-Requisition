from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequisitionRequest(models.Model):
    """Purchase Requisition.

    Created from an approved Material Requisition shortage (see
    material_requisition_ext.py's action_create_purchase_requisition()).
    Routes through Purchase Manager review, amount-based Director approval
    (resolved via ti.approval.route — never a hardcoded threshold), RFQ
    generation, PO confirmation, and receipt tracking.
    """
    _name = 'purchase.requisition.request'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ti.workflow.mixin']
    _order = 'request_date desc, id desc'

    # ------------------------------------------------------------------
    # General Information
    # ------------------------------------------------------------------
    name = fields.Char(
        string='PR No', required=True, readonly=True,
        copy=False, default='New', tracking=True,
    )
    material_requisition_id = fields.Many2one(
        'material.requisition', string='Source MR',
        ondelete='set null', tracking=True,
    )
    department_id = fields.Many2one('hr.department', string='Department')
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True, tracking=True,
    )
    request_date = fields.Date(string='Request Date', default=fields.Date.today, required=True)
    required_date = fields.Date(string='Required By', tracking=True)
    justification = fields.Text(string='Justification / Remarks')

    # Business References (sale_order_id, project_id, manufacturing_order_id,
    # work_order_id, cost_center_id) are inherited from ti.workflow.mixin —
    # deliberately NOT redeclared here. Populated via
    # self._ti_propagate_traceability(source_mr) at creation time.

    # ------------------------------------------------------------------
    # State Machine
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('purchase_manager_review', 'Purchase Manager Review'),
        ('director_approval', 'Awaiting Director Approval'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('po_created', 'PO Created'),
        ('waiting_receipt', 'Waiting Receipt'),
        ('partially_received', 'Partially Received'),
        ('received', 'Received'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ------------------------------------------------------------------
    # Approval Information
    # ------------------------------------------------------------------
    purchase_manager_id = fields.Many2one('res.users', string='Purchase Manager', readonly=True)
    purchase_review_date = fields.Datetime(string='Purchase Review Date', readonly=True)
    director_id = fields.Many2one('res.users', string='Approved By (Director)', readonly=True)
    director_approval_date = fields.Datetime(string='Director Approval Date', readonly=True)
    director_remarks = fields.Text(string='Director Remarks')

    # ------------------------------------------------------------------
    # Financial
    # ------------------------------------------------------------------
    estimated_cost = fields.Float(
        string='Estimated Cost', compute='_compute_estimated_cost', store=True,
        digits='Product Price',
    )
    actual_cost = fields.Float(
        string='Actual Cost', compute='_compute_actual_cost',
        digits='Product Price',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    line_ids = fields.One2many('purchase.requisition.request.line', 'requisition_id', string='Items Required')
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')

    # ------------------------------------------------------------------
    # Smart Button Counts
    # ------------------------------------------------------------------
    rfq_count = fields.Integer(string='RFQs', compute='_compute_counts')
    po_count = fields.Integer(string='POs', compute='_compute_counts')
    purchase_order_count = fields.Integer(string='Purchase Orders', compute='_compute_counts')
    receipt_count = fields.Integer(string='Receipts', compute='_compute_counts')
    audit_log_count = fields.Integer(string='Audit Log', compute='_compute_ti_counts')
    timeline_count = fields.Integer(string='Timeline', compute='_compute_ti_counts')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Purchase Requisition number must be unique.'),
    ]

    # ------------------------------------------------------------------
    # ORM Overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('purchase.requisition.request') or 'New'
                )
        records = super().create(vals_list)
        for rec in records:
            rec._ti_create_timeline_event('created', _('Purchase Requisition Created'))
        return records

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(_('Cannot delete records not in Draft or Cancelled state.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Computed Fields
    # ------------------------------------------------------------------
    @api.depends('line_ids.total_cost')
    def _compute_estimated_cost(self):
        for rec in self:
            rec.estimated_cost = sum(rec.line_ids.mapped('total_cost'))

    def _compute_actual_cost(self):
        for rec in self:
            rec.actual_cost = sum(
                rec.purchase_order_ids.mapped('amount_total')
            )

    def _compute_counts(self):
        for rec in self:
            pos = rec.purchase_order_ids
            rec.purchase_order_count = len(pos)
            rec.rfq_count = len(pos.filtered(lambda po: po.state in ('draft', 'sent')))
            rec.po_count = len(pos.filtered(lambda po: po.state in ('purchase', 'done')))
            rec.receipt_count = self.env['stock.picking'].search_count([
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
                raise UserError(_('Add products to the requisition before submitting.'))
            old_state = rec.state
            rec.write({'state': 'submitted'})
            rec._ti_log_transition(_('Submit'), old_state, 'submitted')
            rec._ti_create_timeline_event('submitted', _('Submitted for Purchase Review'))
            rec._ti_trigger_notifications('submitted')
            rec.message_post(body=_('Purchase Requisition submitted for approval.'))

    def action_purchase_manager_review(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requisitions can enter Purchase Manager review.'))
            old_state = rec.state
            rec.write({
                'state': 'purchase_manager_review',
                'purchase_manager_id': self.env.uid,
                'purchase_review_date': fields.Datetime.now(),
            })
            rec._ti_log_transition(_('Start Purchase Review'), old_state, 'purchase_manager_review')
            rec._ti_create_timeline_event('created', _('Under Purchase Manager Review'))
            rec._ti_trigger_notifications('purchase_manager_review')
            rec.message_post(body=_('Requisition under review by %s.') % self.env.user.name)

    def action_send_for_director_approval(self):
        for rec in self:
            if rec.state != 'purchase_manager_review':
                raise UserError(
                    _('Only requisitions under Purchase Manager review can be sent for Director approval.')
                )
            old_state = rec.state
            rec.write({'state': 'director_approval'})
            rec._ti_log_transition(_('Send for Director Approval'), old_state, 'director_approval')
            rec._ti_create_timeline_event('escalated', _('Sent for Director Approval'))
            rec._ti_trigger_notifications('director_approval')
            rec.message_post(body=_('Requisition sent for Director approval.'))

    def action_director_approve(self, remarks=False):
        for rec in self:
            if rec.state != 'director_approval':
                raise UserError(_('Only requisitions awaiting director approval can be approved.'))
            if not rec._ti_user_can_approve(
                'director_approval', 'approved', amount=rec.estimated_cost
            ):
                raise UserError(
                    _('You are not authorised to approve this requisition at this amount. '
                      'Check the configured approval route thresholds.')
                )
            old_state = rec.state
            rec.write({
                'state': 'approved',
                'director_id': self.env.uid,
                'director_approval_date': fields.Datetime.now(),
                'director_remarks': remarks or rec.director_remarks,
            })
            rec._ti_log_transition(_('Director Approve'), old_state, 'approved', remarks=remarks or '')
            rec._ti_create_timeline_event('approved', _('Approved by Director'))
            rec._ti_trigger_notifications('approved')
            rec.message_post(body=_('Purchase Requisition approved by %s.') % self.env.user.name)

    def action_director_reject(self, remarks=False):
        for rec in self:
            if rec.state != 'director_approval':
                raise UserError(_('Only requisitions awaiting director approval can be rejected.'))
            if not rec._ti_user_can_approve(
                'director_approval', 'approved', amount=rec.estimated_cost
            ):
                raise UserError(_('You are not authorised to reject this requisition.'))
            old_state = rec.state
            rec.write({
                'state': 'purchase_manager_review',
                'director_remarks': remarks or rec.director_remarks,
            })
            rec._ti_log_transition(
                _('Director Reject'), old_state, 'purchase_manager_review', remarks=remarks or ''
            )
            rec._ti_create_timeline_event('rejected', _('Rejected by Director — returned for review'))
            rec._ti_trigger_notifications('director_rejected')
            rec.message_post(
                body=_('Purchase Requisition rejected by Director %s.') % self.env.user.name
            )

    def action_create_rfq(self):
        """Create a draft RFQ (Purchase Order). The purchase user confirms
        the vendor and finalises pricing directly on the resulting PO."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('RFQ can only be created for an approved requisition.'))
        if not self.line_ids:
            raise UserError(_('Add products to the requisition before creating an RFQ.'))

        partner = False
        for line in self.line_ids:
            supplier = line.product_id.seller_ids[:1]
            if supplier:
                partner = supplier.partner_id
                break
        if not partner:
            partner = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)
        if not partner:
            raise UserError(
                _('No vendor found. Configure a supplier for at least one product, '
                  'or create a vendor record, before generating an RFQ.')
            )

        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'notes': _('Generated from Purchase Requisition: %s') % self.name,
        })

        for line in self.line_ids:
            product = line.product_id
            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': line.shortage_qty or line.requested_qty,
                'product_uom': product.uom_po_id.id or product.uom_id.id,
                'price_unit': product.standard_price,
                'date_planned': self.required_date or fields.Date.today(),
            })

        old_state = self.state
        self.purchase_order_ids = [(4, po.id)]
        self.write({'state': 'rfq_created'})
        self._ti_log_transition(_('Create RFQ'), old_state, 'rfq_created')
        self._ti_create_timeline_event('created', _('RFQ Created'), description=po.name)
        self._ti_trigger_notifications('rfq_created')
        self.message_post(body=_('RFQ %s created.') % po.name)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Request for Quotation'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
            'target': 'current',
        }

    def action_confirm_po(self):
        self.ensure_one()
        if self.state != 'rfq_created':
            raise UserError(_('POs can only be confirmed once an RFQ has been created.'))
        draft_pos = self.purchase_order_ids.filtered(lambda po: po.state in ('draft', 'sent'))
        if not draft_pos:
            raise UserError(_('No draft RFQ found to confirm.'))
        for po in draft_pos:
            po.button_confirm()
        old_state = self.state
        self.write({'state': 'po_created'})
        self._ti_log_transition(_('Confirm PO'), old_state, 'po_created')
        self._ti_create_timeline_event('approved', _('Purchase Order Confirmed'))
        self._ti_trigger_notifications('po_created')
        self.message_post(body=_('Purchase Order(s) confirmed.'))

    def action_mark_waiting_receipt(self):
        for rec in self:
            if rec.state != 'po_created':
                raise UserError(_('Only confirmed purchase orders can move to waiting receipt.'))
            old_state = rec.state
            rec.write({'state': 'waiting_receipt'})
            rec._ti_log_transition(_('Mark Waiting Receipt'), old_state, 'waiting_receipt')
            rec._ti_create_timeline_event('created', _('Awaiting Receipt'))
            rec._ti_trigger_notifications('waiting_receipt')
            rec.message_post(body=_('Requisition marked as waiting receipt.'))

    def action_mark_received(self):
        for rec in self:
            if rec.state not in ('waiting_receipt', 'partially_received'):
                raise UserError(_('Only requisitions awaiting receipt can be marked received.'))
            old_state = rec.state
            rec.write({'state': 'received'})
            rec._ti_log_transition(_('Mark Received'), old_state, 'received')
            rec._ti_create_timeline_event('received', _('Materials Received'))
            rec._ti_trigger_notifications('received')
            rec.message_post(body=_('Materials received for %s.') % rec.name)

    def action_done(self):
        for rec in self:
            if rec.state != 'received':
                raise UserError(_('Only received requisitions can be marked done.'))
            old_state = rec.state
            rec.write({'state': 'done'})
            rec._ti_log_transition(_('Mark Done'), old_state, 'done')
            rec._ti_create_timeline_event('completed', _('Purchase Requisition Completed'))
            rec._ti_trigger_notifications('done')
            rec.message_post(body=_('Purchase Requisition marked as Done.'))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise UserError(_('This requisition cannot be cancelled.'))
            old_state = rec.state
            rec.write({'state': 'cancelled'})
            rec._ti_log_transition(_('Cancel'), old_state, 'cancelled')
            rec._ti_create_timeline_event('cancelled', _('Purchase Requisition Cancelled'))
            rec._ti_trigger_notifications('cancelled')
            rec.message_post(body=_('Purchase Requisition cancelled by %s.') % self.env.user.name)

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
    def action_view_purchase_orders(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'target': 'current',
        }
        if self.purchase_order_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.purchase_order_ids.id
        return action

    def action_view_receipts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receipts'),
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
