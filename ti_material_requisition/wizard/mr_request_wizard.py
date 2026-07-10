from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrRequestWizard(models.TransientModel):
    """Quick popup wizard so a Production Supervisor can create and submit
    a Material Requisition in one step without opening the full form."""
    _name = 'mr.request.wizard'
    _description = 'Request Materials Wizard'

    department_id = fields.Many2one('hr.department', string='Department', required=True)
    required_date = fields.Date(string='Required By', required=True, default=fields.Date.today)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Critical'),
    ], string='Priority', default='0')
    remarks = fields.Text(string='Purpose / Remarks')
    line_ids = fields.One2many('mr.request.wizard.line', 'wizard_id', string='Products Required')

    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    project_id = fields.Many2one('project.project', string='Project')
    manufacturing_order_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    work_order_id = fields.Many2one('mrp.workorder', string='Work Order')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill department from the logged-in user's employee record."""
        res = super().default_get(fields_list)
        if 'department_id' in fields_list and not res.get('department_id'):
            employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid)], limit=1
            )
            if employee and employee.department_id:
                res['department_id'] = employee.department_id.id
        return res

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------
    def action_submit_request(self):
        """Create MR and immediately submit it to inventory."""
        self._validate()
        mr = self._build_requisition()
        mr.action_submit()
        return self._open_mr(mr)

    def action_save_draft(self):
        """Create MR in Draft so the supervisor can review before submitting."""
        self._validate()
        mr = self._build_requisition()
        return self._open_mr(mr)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _validate(self):
        if not self.line_ids:
            raise UserError(_('Please add at least one product before proceeding.'))

    def _build_requisition(self):
        line_vals = [
            (0, 0, {
                'product_id': wl.product_id.id,
                'description': wl.product_id.display_name,
                'uom_id': wl.uom_id.id or wl.product_id.uom_id.id,
                'qty_requested': wl.qty_requested,
            })
            for wl in self.line_ids
        ]
        return self.env['material.requisition'].create({
            'department_id': self.department_id.id,
            'required_date': self.required_date,
            'priority': self.priority,
            'remarks': self.remarks,
            'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
            'project_id': self.project_id.id if self.project_id else False,
            'manufacturing_order_id': self.manufacturing_order_id.id if self.manufacturing_order_id else False,
            'work_order_id': self.work_order_id.id if self.work_order_id else False,
            'line_ids': line_vals,
        })

    def _open_mr(self, mr):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requisition'),
            'res_model': 'material.requisition',
            'res_id': mr.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MrRequestWizardLine(models.TransientModel):
    _name = 'mr.request.wizard.line'
    _description = 'Material Requisition Wizard Line'

    wizard_id = fields.Many2one(
        'mr.request.wizard', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit')
    qty_requested = fields.Float(string='Quantity Needed', required=True, default=1.0)
    qty_on_hand = fields.Float(
        string='Currently in Stock', compute='_compute_on_hand',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.depends('product_id')
    def _compute_on_hand(self):
        for line in self:
            line.qty_on_hand = (
                line.product_id.qty_available if line.product_id else 0.0
            )
