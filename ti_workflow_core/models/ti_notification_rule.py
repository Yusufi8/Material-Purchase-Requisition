import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class TiNotificationRule(models.Model):
    """Configurable email and activity notification rules.

    No email template is ever hardcoded inside a model's Python file.
    Operational models call self._ti_trigger_notifications(new_state) and
    this engine resolves which rules apply, who the recipients are, and
    fires the configured email template and/or activity.
    """
    _name = 'ti.notification.rule'
    _description = 'TI Notification Rule'
    _order = 'id'

    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(
        related='model_id.model', string='Model Technical Name',
        store=True, readonly=True,
    )

    trigger_state = fields.Char(string='Trigger State', required=True)

    recipient_type = fields.Selection([
        ('group', 'User Group'),
        ('user_field', 'Field on Document (resolves to user(s))'),
    ], string='Recipient Type', required=True, default='group')

    recipient_group_ids = fields.Many2many('res.groups', string='Recipient Group(s)')
    recipient_field = fields.Char(
        string='Recipient Field',
        help='Technical field name (dot path allowed) on the document that '
             'resolves to a res.users record, e.g. requested_by',
    )

    email_template_id = fields.Many2one('mail.template', string='Email Template')
    send_activity = fields.Boolean(string='Also Create Activity', default=False)
    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type')
    activity_note_template = fields.Text(string='Activity Note')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
    )

    def get_recipients(self, document):
        """Resolve the res.users recordset for this rule against a document record."""
        self.ensure_one()
        users = self.env['res.users']
        if self.recipient_type == 'group':
            for group in self.recipient_group_ids:
                users |= group.users
        elif self.recipient_type == 'user_field' and self.recipient_field:
            try:
                value = document
                for part in self.recipient_field.split('.'):
                    value = getattr(value, part)
                if value and getattr(value, '_name', False) == 'res.users':
                    users |= value
            except Exception:
                _logger.warning(
                    'TI Notification Rule "%s": could not resolve recipient_field '
                    '"%s" on %s', self.name, self.recipient_field, document,
                )
        return users
