from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TiApprovalActionWizard(models.TransientModel):
    """Generic approve/reject wizard with a remarks field.

    Any document model that implements action_director_approve() and
    action_director_reject() can reuse this single wizard instead of each
    operational module building its own popup. This is the kind of reusable
    service the architecture calls for — one wizard, called from MR, PR,
    and any future approval-gated document.
    """
    _name = 'ti.approval.action.wizard'
    _description = 'TI Generic Approval Action Wizard'

    res_model = fields.Char(string='Document Model', required=True)
    res_id = fields.Integer(string='Document ID', required=True)
    document_ref = fields.Char(string='Document Reference', compute='_compute_document_ref')

    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Decision', required=True, default='approve')

    remarks = fields.Text(string='Remarks')

    @api.depends('res_model', 'res_id')
    def _compute_document_ref(self):
        for wiz in self:
            ref = ''
            if wiz.res_model and wiz.res_id:
                record = self.env[wiz.res_model].browse(wiz.res_id)
                if record.exists():
                    ref = record.display_name
            wiz.document_ref = ref

    def action_confirm(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_('No source document found for this approval action.'))

        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_('The source document no longer exists.'))

        method_name = 'action_director_approve' if self.action_type == 'approve' else 'action_director_reject'
        if not hasattr(record, method_name):
            raise UserError(
                _('This document type does not support the "%s" action.') % method_name
            )

        method = getattr(record, method_name)
        try:
            method(remarks=self.remarks)
        except TypeError:
            # Target method does not accept a remarks kwarg — call without it
            # and post the remarks to the chatter separately instead.
            method()
            if self.remarks and hasattr(record, 'message_post'):
                record.message_post(body=self.remarks)

        return {'type': 'ir.actions.act_window_close'}
