# TI Purchase Requisition

Part of the T&I Projects Integrated Operations Workflow Platform.

## Depends on

- `ti_workflow_core` (audit trail, timeline, approval routing, notification
  engine, shared groups, shared `ti.approval.action.wizard`)
- `ti_material_requisition` (the source document this module extends)
- `purchase`, `stock` (standard Odoo 16 Community apps)

## What this module owns

- `purchase.requisition.request`
- `purchase.requisition.request.line`

## What this module extends (not owns)

`material.requisition` (from `ti_material_requisition`), via
`models/material_requisition_ext.py`:
- `purchase_requisition_ids` / `purchase_requisition_count`
- `action_create_purchase_requisition()` — director_approved → purchase_requisition_created
- `_get_availability_check_states()` override — adds `purchase_requisition_created`
  to the states from which Inventory can re-run availability, using the
  extension hook `ti_material_requisition` was built with, not a duplicate method

This is the intended direction of extension: the downstream module (this
one) reaches back into the upstream model it depends on, rather than the
upstream module reaching forward into a model it doesn't know exists.

## Director approval threshold (₹2,00,000) — data, not code

`data/approval_routes.xml` defines two `ti.approval.route` records on the
`director_approval → approved` transition:

| Estimated Cost | Approver |
|---|---|
| < ₹2,00,000 | Operations Director |
| ≥ ₹2,00,000 | Managing Director |

To change the threshold, edit `amount_min` / `amount_max` on these two
records from Settings → TI Workflow Settings → Approval Routes. No code
change, no module upgrade required. Because `group_managing_director`
implies `group_operations_director` in `ti_workflow_core`'s security
hierarchy, a Managing Director can also approve requisitions under the
standard threshold — a Director's authority is never a ceiling.

## No new wizard here

The "Director Approve" / "Director Reject" buttons open
`ti.approval.action.wizard` from `ti_workflow_core` — the same wizard
`ti_material_requisition` already uses for its own director-approval step.
See `wizard/__init__.py` for why no PR-specific wizard was built.

## Workflow

```
draft → submitted → purchase_manager_review → director_approval
                                                      │
                                    ┌─────────────────┴─────────────────┐
                              (approve)                            (reject)
                                    │                                    │
                                approved                     back to purchase_manager_review
                                    │
                            action_create_rfq
                                    │
                               rfq_created
                                    │
                            action_confirm_po
                                    │
                                po_created
                                    │
                        action_mark_waiting_receipt
                                    │
                               waiting_receipt
                                    │
                          action_mark_received
                                    │
                                 received
                                    │
                              action_done
                                    │
                                   done
```

(any non-terminal state) → cancelled → (reset) → draft

## Extension points for ti_procurement

1. Vendor comparison across multiple RFQs for the same PR (this module
   creates exactly one RFQ per `action_create_rfq()` call, assigned to the
   first vendor found via `product.supplierinfo` or the first active
   supplier — a fixed, simple default deliberately left for
   `ti_procurement` to make configurable).
2. `purchase.requisition.request.line.actual_cost` is a plain, manually
   editable Float here. Automatic reconciliation against the confirmed PO
   line price belongs in `ti_procurement`.
3. `action_confirm_po()` confirms every draft/sent PO linked to the PR
   in one call. Per-PO partial confirmation (if the vendor decision only
   covers some lines) is a `ti_procurement` concern.
