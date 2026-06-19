from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequisitionRequest(models.Model):
    _name = 'purchase.requisition.request'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(
        string='PR No',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )
    material_requisition_id = fields.Many2one(
        'material.requisition',
        string='Material Requisition',
        ondelete='set null',
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.today,
        required=True,
    )
    department_id = fields.Many2one('hr.department', string='Department')
    required_date = fields.Date(string='Required By', tracking=True)
    justification = fields.Text(string='Justification / Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True, index=True)

    line_ids = fields.One2many(
        'purchase.requisition.request.line',
        'requisition_id',
        string='Products Required',
    )
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')
    purchase_order_count = fields.Integer(compute='_compute_counts', string='POs')
    receipt_count = fields.Integer(compute='_compute_counts', string='Receipts')

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
                    self.env['ir.sequence'].next_by_code('purchase.requisition.request')
                    or 'New'
                )
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(_('Cannot delete records not in Draft or Cancelled state.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('purchase_order_ids', 'name')
    def _compute_counts(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)
            rec.receipt_count = self.env['stock.picking'].search_count([
                ('origin', '=', rec.name),
            ])

    # ------------------------------------------------------------------
    # Workflow Actions
    # ------------------------------------------------------------------
    def action_submit(self):
        self.write({'state': 'submitted'})
        self.message_post(body=_('Purchase Requisition submitted for approval.'))

    def action_approve(self):
        self.write({'state': 'approved'})
        self.message_post(body=_('Purchase Requisition approved.'))

        purch_group = self.env.ref(
            'material_purchase_requisition.group_purchase_user_custom',
            raise_if_not_found=False,
        )
        if purch_group and purch_group.users:
            act_type = self.env.ref('mail.mail_activity_data_todo')
            for user in purch_group.users:
                self.activity_schedule(
                    act_type.id,
                    user_id=user.id,
                    note=_('Purchase Requisition %s approved — please create RFQ.') % self.name,
                )

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Purchase Requisition cancelled.'))

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_done(self):
        self.write({'state': 'done'})
        self.message_post(body=_('Purchase Requisition marked as Done.'))

    def action_create_rfq(self):
        """
        Create a draft RFQ (Purchase Order) with lines from this requisition.
        The purchase user selects/confirms the vendor on the resulting PO form.
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add products to the requisition before creating an RFQ.'))

        # Try to find a default vendor from any line's product supplierinfo
        partner = None
        for line in self.line_ids:
            supplier = line.product_id.seller_ids[:1]
            if supplier:
                partner = supplier.partner_id
                break
        if not partner:
            # Fall back to first supplier in the system
            partner = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)

        po_vals = {
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'notes': _('Generated from Purchase Requisition: %s') % self.name,
        }
        if partner:
            po_vals['partner_id'] = partner.id

        po = self.env['purchase.order'].create(po_vals)

        for line in self.line_ids:
            product = line.product_id
            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': line.shortage_qty or line.requested_qty,
                'product_uom': product.uom_po_id.id,
                'price_unit': product.standard_price,
                'date_planned': self.required_date or fields.Date.today(),
            })

        self.purchase_order_ids = [(4, po.id)]
        self.write({'state': 'rfq_created'})
        self.message_post(
            body=_('RFQ <a href="#">%s</a> created.') % po.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Request for Quotation'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
            'target': 'current',
        }

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