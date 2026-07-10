# This module intentionally defines no new wizard models.
#
# The "Director Approve" / "Director Reject" actions on
# purchase.requisition.request open ti.approval.action.wizard from
# ti_workflow_core — the same generic wizard already used by
# ti_material_requisition for its own director-approval step. Building a
# second, near-identical wizard here would duplicate business logic that
# ti_workflow_core already provides. See views/actions.xml for the two
# window actions that open it with the correct context defaults.
