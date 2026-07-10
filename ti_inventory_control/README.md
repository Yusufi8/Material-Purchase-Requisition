# TI Inventory Control

Part of the T&I Projects Integrated Operations Workflow Platform.

## Depends on

- `ti_workflow_core` (audit trail, timeline)
- `ti_material_requisition` (the model this module extends)
- `stock`

## Why this module is smaller than you might expect

`ti_material_requisition` already implements full-quantity stock
reservation (`action_reserve_stock`) and full-quantity issue
(`action_issue_materials`) directly, using `stock.quant` /
`stock.picking` / `stock.move` — deliberately, so a Material Requisition
is fully usable standalone without this module, the same way
`ti_material_requisition` itself is usable without
`ti_purchase_requisition`.

This module adds only what that standalone path doesn't cover:

- **Partial issue** (`ti.issue.materials.wizard`) — issue less than the
  full approved quantity on a line, and run it again later for what's
  left. The one-shot "Issue Materials" button still exists for the common
  case; this is the alternative for splitting an issue across transfers.
- **Returns** (`ti.stock.return.wizard`) — send previously issued
  materials back to stock, decrementing `qty_issued` accordingly.
- **Fulfilment tracking fields** on `material.requisition`
  (`total_requested_qty`, `total_approved_qty`, `total_issued_qty`,
  `total_pending_qty`, `fulfillment_rate`, `is_fully_issued`) — not
  consumed by anything in this module itself, but built for
  `ti_management_dashboard`'s Inventory Dashboard.

## A deliberate non-decision

Both wizards check their own local state tuples
(`('ready_to_issue', 'stock_reserved', 'director_approved')` and
`('issued', 'completed')`) rather than a shared hook like
`ti_material_requisition`'s `_get_availability_check_states()`. That hook
exists because `ti_purchase_requisition` *overrides* an existing method
(`action_check_availability`'s precondition) and needed an extension
point to do it without duplicating the method. These two wizards don't
override anything — they're new functionality operating at a different
granularity (partial, possibly repeated) than the full-quantity actions
already in `ti_material_requisition`. A shared tuple would be
consistency for its own sake, not a fix for actual duplicated logic.

## Non-state-changing audit entries

A partial issue that doesn't fully complete the line, and every return,
don't move `material.requisition.state`. Both still call
`_ti_log_transition()` with `old_state == new_state` — the audit
trail's purpose ("nothing should change silently") applies to any action
worth recording, not only ones that flip a state.

## Extension points for ti_procurement / ti_management_dashboard

1. The fulfilment fields computed here are ready to drive the Inventory
   Dashboard's "Reserved Stock" / low-stock views without needing any
   further schema changes.
2. Neither wizard currently checks whether a *return* should also revert
   `is_fully_issued`-driven state (e.g. moving `issued` back toward
   `partially_available` if enough is returned). Left as-is deliberately —
   a returned-then-what business rule wasn't specified, and inventing one
   silently would be a bigger decision than this module should make alone.
