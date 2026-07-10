import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class TiWorkflowMixin(models.AbstractModel):
    """Reusable mixin inherited by every document model in the platform.

    Provides:
      - The four traceability FK fields (Sales Order / Project /
        Manufacturing Order / Work Order) plus a Cost Centre field, so no
        document is ever an orphan.
      - Helper methods that wrap ti_workflow_core's audit, timeline,
        notification, and approval-routing engines, so operational
        modules never reimplement this logic.

    Usage in an operational model::

        _inherit = ['mail.thread', 'mail.activity.mixin', 'ti.workflow.mixin']

    NOTE: mail.activity.mixin is required on the consuming model if you
    want _ti_trigger_notifications() to be able to schedule activities
    (send_activity=True rules). If the consuming model does not inherit
    mail.activity.mixin, activity scheduling is silently skipped.
    """
    _name = 'ti.workflow.mixin'
    _description = 'TI Workflow Mixin'

    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    project_id = fields.Many2one('project.project', string='Project')
    manufacturing_order_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    work_order_id = fields.Many2one('mrp.workorder', string='Work Order')
    cost_center_id = fields.Many2one('account.analytic.account', string='Cost Centre')

    # ------------------------------------------------------------------
    # Audit Trail
    # ------------------------------------------------------------------
    def _ti_log_transition(self, action, old_state, new_state, remarks=''):
        """Write one immutable ti.workflow.log entry for this transition."""
        self.ensure_one()
        department_id = False
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1,
        )
        if employee and employee.department_id:
            department_id = employee.department_id.id

        return self.env['ti.workflow.log'].sudo().create({
            'document_model': self._name,
            'document_id': self.id,
            'document_ref': self.display_name,
            'action': action,
            'old_state': old_state or '',
            'new_state': new_state or '',
            'user_id': self.env.uid,
            'department_id': department_id,
            'remarks': remarks or '',
            'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
            'project_id': self.project_id.id if self.project_id else False,
            'manufacturing_order_id': self.manufacturing_order_id.id if self.manufacturing_order_id else False,
            'work_order_id': self.work_order_id.id if self.work_order_id else False,
            'company_id': self.env.company.id,
        })

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------
    _TI_TIMELINE_ICONS = {
        'created': 'fa-plus-circle',
        'submitted': 'fa-paper-plane',
        'approved': 'fa-check-circle',
        'rejected': 'fa-times-circle',
        'escalated': 'fa-exclamation-triangle',
        'issued': 'fa-truck',
        'received': 'fa-inbox',
        'completed': 'fa-flag-checkered',
        'cancelled': 'fa-ban',
    }
    _TI_TIMELINE_COLORS = {
        'created': 'info',
        'submitted': 'info',
        'approved': 'success',
        'rejected': 'danger',
        'escalated': 'warning',
        'issued': 'success',
        'received': 'success',
        'completed': 'success',
        'cancelled': 'muted',
    }

    def _ti_create_timeline_event(self, event_type, event_name, description=''):
        """Write one ti.document.timeline entry for this document."""
        self.ensure_one()
        return self.env['ti.document.timeline'].sudo().create({
            'document_model': self._name,
            'document_id': self.id,
            'document_ref': self.display_name,
            'event_type': event_type,
            'event_name': event_name,
            'description': description or '',
            'user_id': self.env.uid,
            'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
            'project_id': self.project_id.id if self.project_id else False,
            'manufacturing_order_id': self.manufacturing_order_id.id if self.manufacturing_order_id else False,
            'work_order_id': self.work_order_id.id if self.work_order_id else False,
            'icon': self._TI_TIMELINE_ICONS.get(event_type, 'fa-circle'),
            'color': self._TI_TIMELINE_COLORS.get(event_type, 'info'),
            'company_id': self.env.company.id,
        })

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _ti_trigger_notifications(self, trigger_state):
        """Evaluate ti.notification.rule records for this model + state and fire them."""
        self.ensure_one()
        rules = self.env['ti.notification.rule'].sudo().search([
            ('model_name', '=', self._name),
            ('trigger_state', '=', trigger_state),
            ('active', '=', True),
        ])
        for rule in rules:
            recipients = rule.get_recipients(self)
            if not recipients:
                continue

            if rule.email_template_id:
                for user in recipients:
                    if not user.email:
                        continue
                    try:
                        rule.email_template_id.sudo().send_mail(
                            self.id,
                            force_send=False,
                            email_values={'email_to': user.email},
                        )
                    except Exception:
                        _logger.exception(
                            'TI Notification Rule "%s": failed to email %s for %s(%s)',
                            rule.name, user.email, self._name, self.id,
                        )

            if rule.send_activity and rule.activity_type_id and hasattr(self, 'activity_schedule'):
                note = rule.activity_note_template or _('Action required on %s') % self.display_name
                for user in recipients:
                    try:
                        self.activity_schedule(
                            activity_type_id=rule.activity_type_id.id,
                            user_id=user.id,
                            note=note,
                        )
                    except Exception:
                        _logger.exception(
                            'TI Notification Rule "%s": failed to schedule activity for '
                            '%s on %s(%s)', rule.name, user.name, self._name, self.id,
                        )

    # ------------------------------------------------------------------
    # Approval Routing
    # ------------------------------------------------------------------
    def _ti_check_approval_route(self, state_from, state_to, amount=None):
        """Return the ti.approval.route record matching this transition (and amount)."""
        self.ensure_one()
        routes = self.env['ti.approval.route'].sudo().search([
            ('model_name', '=', self._name),
            ('state_from', '=', state_from),
            ('state_to', '=', state_to),
            ('active', '=', True),
        ], order='sequence, id')
        for route in routes:
            if route.matches(self._name, state_from, state_to, amount=amount):
                return route
        return self.env['ti.approval.route']

    def _ti_get_approver_groups(self, state_from, state_to, amount=None):
        """Return the res.groups recordset authorised to approve this transition."""
        route = self._ti_check_approval_route(state_from, state_to, amount=amount)
        return route.approver_group_ids if route else self.env['res.groups']

    def _ti_user_can_approve(self, state_from, state_to, amount=None, user=None):
        """Check whether the given (or current) user may approve this transition.

        Returns True if no route is configured for this transition (i.e. no
        restriction has been set up), so this should be combined with normal
        ir.model.access / record rule checks rather than relied on alone.
        """
        user = user or self.env.user
        groups = self._ti_get_approver_groups(state_from, state_to, amount=amount)
        if not groups:
            return True
        return bool(groups & user.groups_id)

    # ------------------------------------------------------------------
    # Traceability propagation
    # ------------------------------------------------------------------
    def _ti_propagate_traceability(self, source_record):
        """Copy the traceability FKs (and cost centre) from source_record onto self."""
        self.ensure_one()
        vals = {}
        for field_name in (
            'sale_order_id', 'project_id', 'manufacturing_order_id',
            'work_order_id', 'cost_center_id',
        ):
            if field_name in self._fields and hasattr(source_record, field_name):
                value = getattr(source_record, field_name)
                vals[field_name] = value.id if value else False
        if vals:
            self.write(vals)
        return self
