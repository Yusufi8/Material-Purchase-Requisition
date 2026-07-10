from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TiWorkflowLog(models.Model):
    """Immutable audit trail.

    One record is written per workflow transition by
    ti.workflow.mixin._ti_log_transition(). Records are never updated or
    deleted — write() and unlink() are hard-blocked below so that nothing
    in the platform can change silently, per the company's audit
    requirements.
    """
    _name = 'ti.workflow.log'
    _description = 'TI Workflow Audit Log'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    document_model = fields.Char(string='Document Model', required=True, index=True)
    document_id = fields.Integer(string='Document ID', required=True, index=True)
    document_ref = fields.Char(string='Document Reference', index=True)

    action = fields.Char(string='Action', required=True)
    old_state = fields.Char(string='Old State')
    new_state = fields.Char(string='New State')

    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        default=lambda self: self.env.user, index=True,
    )
    department_id = fields.Many2one('hr.department', string='Department')
    date = fields.Datetime(
        string='Date', required=True,
        default=fields.Datetime.now, readonly=True, index=True,
    )
    remarks = fields.Text(string='Remarks')

    # Traceability snapshot at the time of the action
    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    project_id = fields.Many2one('project.project', string='Project')
    manufacturing_order_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    work_order_id = fields.Many2one('mrp.workorder', string='Work Order')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            'unique_transition',
            'unique(document_model, document_id, old_state, new_state, date, user_id)',
            'A duplicate workflow log entry cannot be created for the same '
            'transition at the same time by the same user.',
        ),
    ]

    @api.depends('document_ref', 'document_model', 'action', 'old_state', 'new_state')
    def _compute_name(self):
        for rec in self:
            ref = rec.document_ref or rec.document_model or _('Document')
            old = rec.old_state or '-'
            new = rec.new_state or '-'
            rec.name = '%s — %s (%s → %s)' % (ref, rec.action or '', old, new)

    def write(self, vals):
        raise UserError(_('Workflow log entries are immutable and cannot be modified.'))

    def unlink(self):
        raise UserError(_('Workflow log entries are immutable and cannot be deleted.'))
