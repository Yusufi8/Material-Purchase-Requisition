from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MaterialRequisition(models.Model):
    _name = 'material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Requisition No',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    required_date = fields.Date(
        string='Required By',
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        tracking=True,
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    supervisor_id = fields.Many2one(
        'res.users',
        string='Approved By (Supervisor)',
        tracking=True,
    )
    remarks = fields.Text(string='Purpose / Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('inventory_review', 'Inventory Review'),
        ('partially_available', 'Partially Available'),
        ('ready_to_issue', 'Ready to Issue'),
        ('issued', 'Issued'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True, index=True)

    line_ids = fields.One2many(
        'material.requisition.line',
        'requisition_id',
        string='Requested Items',
    )
    purchase_requisition_ids = fields.One2many(
        'purchase.requisition.request',
        'material_requisition_id',
        string='Purchase Requisitions',
    )

    # Smart button counts
    purchase_requisition_count = fields.Integer(
        compute='_compute_smart_counts',
        string='Purchase Requisitions',
    )
    stock_picking_count = fields.Integer(
        compute='_compute_smart_counts',
        string='Transfers',
    )

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
                    self.env['ir.sequence'].next_by_code('material.requisition')
                    or 'New'
                )
        return super().create(vals_list)

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
    @api.depends('purchase_requisition_ids', 'name')
    def _compute_smart_counts(self):
        for rec in self:
            rec.purchase_requisition_count = len(rec.purchase_requisition_ids)
            rec.stock_picking_count = self.env['stock.picking'].search_count([
                ('origin', '=', rec.name),
            ])

    # ------------------------------------------------------------------
    # Workflow Buttons
    # ------------------------------------------------------------------
    def action_submit(self):
        """Production Supervisor submits request → notifies Inventory Manager."""
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add at least one product before submitting.'))
            rec.write({'state': 'submitted'})
            rec.message_post(
                body=_('Material Requisition submitted by %s.') % rec.requested_by.name
            )
            # Notify inventory managers via activity
            inv_group = self.env.ref(
                'material_purchase_requisition.group_inventory_manager',
                raise_if_not_found=False,
            )
            if inv_group and inv_group.users:
                act_type = self.env.ref('mail.mail_activity_data_todo')
                for user in inv_group.users:
                    rec.activity_schedule(
                        act_type.id,
                        user_id=user.id,
                        note=_('New material requisition %s awaiting inventory review.') % rec.name,
                    )

    def action_set_inventory_review(self):
        """Inventory Manager opens the requisition for review."""
        self.write({'state': 'inventory_review'})
        self.message_post(body=_('Requisition under inventory review.'))

    def action_check_availability(self):
        """
        Check current stock for each line.
        Sets qty_approved and moves to correct state.
        """
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('No items to check.'))

            shortage_found = False
            for line in rec.line_ids:
                available = line.qty_available  # computed by the line model
                if available >= line.qty_requested:
                    line.qty_approved = line.qty_requested
                else:
                    shortage_found = True
                    line.qty_approved = available

            new_state = 'partially_available' if shortage_found else 'ready_to_issue'
            rec.write({'state': new_state})
            rec.message_post(
                body=_('Availability checked. Status: %s') % dict(
                    rec._fields['state'].selection
                ).get(new_state)
            )

    def action_issue_materials(self):
        """Create an internal stock transfer and move stock to production."""
        self.ensure_one()

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
        self.message_post(
            body=_('Materials issued via transfer <a href="#">%s</a>.') % picking.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_purchase_requisition(self):
        """Create a Purchase Requisition for all lines with shortages."""
        self.ensure_one()
        shortage_lines = self.line_ids.filtered(lambda l: l.shortage_qty > 0)
        if not shortage_lines:
            raise UserError(_('No shortage found. All items are available in stock.'))

        pr = self.env['purchase.requisition.request'].create({
            'material_requisition_id': self.id,
            'department_id': self.department_id.id,
            'requested_by': self.requested_by.id,
            'required_date': self.required_date,
        })
        for line in shortage_lines:
            self.env['purchase.requisition.request.line'].create({
                'requisition_id': pr.id,
                'product_id': line.product_id.id,
                'requested_qty': line.shortage_qty,
                'available_qty': line.qty_available,
                'shortage_qty': line.shortage_qty,
                'remarks': line.description or '',
            })

        # Notify purchase team
        purch_group = self.env.ref(
            'material_purchase_requisition.group_purchase_user_custom',
            raise_if_not_found=False,
        )
        if purch_group and purch_group.users:
            act_type = self.env.ref('mail.mail_activity_data_todo')
            for user in purch_group.users:
                pr.activity_schedule(
                    act_type.id,
                    user_id=user.id,
                    note=_('New purchase requisition %s raised for material shortage.') % pr.name,
                )

        self.message_post(
            body=_('Purchase Requisition <a href="#">%s</a> created for shortage items.') % pr.name
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requisition'),
            'res_model': 'purchase.requisition.request',
            'view_mode': 'form',
            'res_id': pr.id,
            'target': 'current',
        }

    def action_mark_completed(self):
        self.write({'state': 'completed'})
        self.message_post(body=_('Requisition marked as Completed.'))

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Requisition cancelled.'))

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # Smart Button Actions
    # ------------------------------------------------------------------
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