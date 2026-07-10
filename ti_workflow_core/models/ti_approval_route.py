from odoo import fields, models


class TiApprovalRoute(models.Model):
    """Configurable approval routing.

    Replaces hardcoded approval logic ("if amount >= 200000: managing
    director") in every operational module. A route says: for this model,
    for this state transition, (optionally within this amount band), these
    groups may approve. Operational models call
    self._ti_check_approval_route(...) instead of encoding any threshold
    in Python — so changing the Operations Director / Managing Director
    cutover amount is a data change, not a code change.
    """
    _name = 'ti.approval.route'
    _description = 'TI Approval Route'
    _order = 'sequence, id'

    name = fields.Char(string='Route Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(
        related='model_id.model', string='Model Technical Name',
        store=True, readonly=True,
    )

    state_from = fields.Char(string='From State', required=True)
    state_to = fields.Char(string='To State', required=True)

    approver_group_ids = fields.Many2many('res.groups', string='Approver Group(s)', required=True)
    require_all_approvers = fields.Boolean(
        string='Require All Approver Groups',
        default=False,
        help='If checked, a member of every listed group must approve. '
             'If unchecked, any one approver from any listed group can approve.',
    )

    amount_field = fields.Char(
        string='Amount Field',
        help='Technical field name on the target model used for amount-based '
             'routing, e.g. estimated_cost. Leave blank for routes that do not '
             'depend on a monetary amount.',
    )
    amount_min = fields.Float(string='Amount Min', default=0.0)
    amount_max = fields.Float(
        string='Amount Max', default=0.0,
        help='0 means no upper limit.',
    )

    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
    )

    def matches(self, model_name, state_from, state_to, amount=None):
        """Return True if this route applies to the given transition and amount."""
        self.ensure_one()
        if self.model_name != model_name:
            return False
        if self.state_from != state_from or self.state_to != state_to:
            return False
        if self.amount_field:
            amt = amount or 0.0
            if amt < self.amount_min:
                return False
            if self.amount_max and amt >= self.amount_max:
                return False
        return True
