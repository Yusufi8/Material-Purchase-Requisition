from odoo import fields, models


class TiDocumentTimeline(models.Model):
    """Chronological event timeline for a document.

    Distinct from ti.workflow.log: the log is a technical audit record
    (every transition, for compliance); the timeline is a curated set of
    business-meaningful events meant to be displayed to end users on a
    document's form view (e.g. 'Shortage Found', 'Director Approved',
    'RFQ Created').
    """
    _name = 'ti.document.timeline'
    _description = 'TI Document Timeline'
    _order = 'event_date desc, id desc'
    _rec_name = 'event_name'

    document_model = fields.Char(string='Document Model', required=True, index=True)
    document_id = fields.Integer(string='Document ID', required=True, index=True)
    document_ref = fields.Char(string='Document Reference', index=True)

    event_type = fields.Selection([
        ('created', 'Created'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
        ('issued', 'Issued'),
        ('received', 'Received'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Event Type', required=True)

    event_name = fields.Char(string='Event', required=True)
    event_date = fields.Datetime(
        string='Event Date', required=True,
        default=fields.Datetime.now, readonly=True, index=True,
    )
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    description = fields.Text(string='Description')

    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    project_id = fields.Many2one('project.project', string='Project')
    manufacturing_order_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    work_order_id = fields.Many2one('mrp.workorder', string='Work Order')

    icon = fields.Char(string='Icon', default='fa-circle')
    color = fields.Selection([
        ('muted', 'Muted'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('danger', 'Danger'),
    ], string='Color', default='info')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
    )
