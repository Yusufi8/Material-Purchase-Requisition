# TI Material Requisition

Part of the T&I Projects Integrated Operations Workflow Platform.

## Depends on

- `ti_workflow_core` (required — audit trail, timeline, approval routing,
  notification engine, and the 9 platform-wide security groups)
- `mrp`, `stock`, `hr`, `project` (standard Odoo 16 Community apps)

## What this module owns

- `material.requisition`
- `material.requisition.line`
- `mr.request.wizard` / `mr.request.wizard.line` (quick-request popup)
- `ti.inventory.review.wizard` / `.line` (manual availability override)

## Workflow

```
draft → submitted → supervisor_approved → inventory_review
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        │                                           │
                  (all in stock)                            (shortage found)
                        │                                           │
                  ready_to_issue                          partially_available
                        │                                           │
                 [Reserve Stock]                      action_request_director_approval
                        │                                           │
                 stock_reserved                        director_approval_required
                        │                                    │             │
                        │                              (approve)      (reject)
                        │                                    │             │
                        │                          director_approved  → back to
                        │                                    │        inventory_review
                        └──────────────┬─────────────────────┘
                                       │
                              action_issue_materials
                                       │
                                    issued
                                       │
                              action_mark_completed
                                       │
                                   completed

(any non-terminal state) → cancelled → (reset) → draft
```

## Why this module does NOT create Purchase Requisitions

`ti_material_requisition` does not depend on `ti_purchase_requisition` and
therefore has no way to safely reference `purchase.requisition.request` in
Python — doing so would create a hidden runtime dependency on a module not
declared in `depends`, which breaks if MR is ever installed without PR.

The state selection on `material.requisition` includes
`purchase_requisition_created` for statusbar continuity, but no method in
this module transitions into it. `ti_purchase_requisition` (which depends
on this module) adds that transition, the `action_create_purchase_requisition()`
method, the `purchase_requisition_ids` / `purchase_requisition_count` smart
button, and the "Request Purchase" button — all via `_inherit =
'material.requisition'` in that module's own model extension. This is the
correct direction for the dependency: the module that knows about the
downstream model extends the upstream one, not the other way around.

## Reused from ti_workflow_core (not duplicated here)

- `_ti_log_transition()` — every state change writes to `ti.workflow.log`
- `_ti_create_timeline_event()` — every state change writes to `ti.document.timeline`
- `_ti_trigger_notifications()` — email/activity dispatch driven by
  `ti.notification.rule` data records in `data/notification_rules.xml`
- `_ti_check_approval_route()` / `_ti_user_can_approve()` — director
  approval on the shortage escalation is resolved via
  `data/approval_routes.xml`, not hardcoded in Python
- `ti.approval.action.wizard` — the "Director Approve" / "Director Reject"
  header buttons open this shared wizard from `ti_workflow_core` rather
  than each module building its own approve/reject popup

## Extension points for ti_purchase_requisition

1. `_inherit = 'material.requisition'` and add:
   - `purchase_requisition_ids` (One2many to `purchase.requisition.request`)
   - `purchase_requisition_count` (compute)
   - `action_create_purchase_requisition()` (director_approved →
     purchase_requisition_created)
2. Inherit `view_material_requisition_form` to add the PR smart button and
   the "Request Purchase" header button.
3. Add a `ti.approval.route` / `ti.notification.rule` data record in the PR
   module for the PR's own director approval gate (amount-based, per the
   ₹2,00,000 threshold) — do not reuse the MR shortage route, they are
   different transitions on a different model.
4. Override `_get_availability_check_states()` (returns
   `('inventory_review', 'director_approved')` here) to also include
   `'purchase_requisition_created'`, so Inventory can re-run availability
   once a linked Purchase Requisition's shortage has been received. Both
   `action_check_availability()` and the Inventory Review Wizard read this
   hook rather than hardcoding the tuple, so overriding it is sufficient —
   no method needs to be duplicated. The corresponding header buttons'
   `attrs` will need a matching view-inheritance update (xpath on
   `string='Check Availability'` / `string='Review &amp; Approve Qty'`,
   not on `name`, since `type="action"` button `name` attributes are
   resolved to numeric IDs at data-load time and can't be xpath-matched
   by their original `%(xmlid)d` text from an inheriting view).
