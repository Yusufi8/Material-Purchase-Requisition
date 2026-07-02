# Material & Purchase Requisition Architecture Review

## Scope and source-of-truth decisions

This review is the first migration artifact for modernizing the legacy `material_purchase_requisition` addon into the approved Odoo 16 Community architecture. The current repository contains a single combined addon; the target architecture requires separate responsibility boundaries:

1. `ti_workflow_core` owns shared workflow, approval, timeline, notification, mail/activity, and route services.
2. `ti_material_requisition` owns material requisition and material requisition lines only.
3. `ti_purchase_requisition` owns purchase requisition and purchase requisition lines only.
4. `ti_inventory_control` owns stock reservation, material issue, returns, transfers, stock moves, and pickings.
5. `ti_procurement` owns RFQ generation, vendor comparison, purchase orders, vendor performance, and receipt tracking.
6. `ti_management_dashboard` owns dashboards, KPIs, reports, analytics, and executive visibility.

The current addon is the functional reference, not the architectural reference. Working behavior should be retained unless it conflicts with those boundaries.

## Repository file inventory

| File | Purpose | Dependencies | Existing functionality | Problems | Planned improvement | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `material_purchase_requisition/__manifest__.py` | Declares the combined legacy addon. | `base`, `mail`, `stock`, `purchase`, `hr`, `mrp`, `sale`, `project`, `analytic`. | Installs material and purchase flows together. | Combines material, purchase, inventory, and procurement dependencies in one module. | Split manifest responsibilities across target modules and depend on `ti_workflow_core` where workflow services are used. | Refactor. |
| `material_purchase_requisition/__init__.py` | Loads model and wizard packages. | Local `models`, `wizard`. | Imports all legacy code. | Loads combined business domains together. | Replace with separate module initializers during split. | Refactor. |
| `material_purchase_requisition/models/__init__.py` | Loads legacy ORM models. | Local material and purchase model files. | Registers MR, MR line, PR, and PR line models. | Cross-domain model registration in one addon. | Move registrations into `ti_material_requisition` and `ti_purchase_requisition`. | Refactor. |
| `material_purchase_requisition/models/material_requisition.py` | Material requisition header model and workflow actions. | `mail`, `stock`, purchase requisition models, security group XML IDs. | Creates material requests, checks shortages, issues stock via pickings, creates purchase requisitions, posts chatter, schedules activities. | Violates target boundaries by creating stock pickings/moves and purchase requisitions directly; duplicates workflow/notification logic that belongs in `ti_workflow_core`; lacks explicit multi-company fields. | Retain MR fields and shortage calculation; move stock issue to `ti_inventory_control`; replace PR creation with extension hooks overridden by `ti_purchase_requisition`; call workflow-core transition and notification helpers. | Refactor / move selected features. |
| `material_purchase_requisition/models/material_requisition_line.py` | Material requisition line model. | `product.product`, `uom.uom`, MR state. | Captures requested/approved/issued quantities and computes stock shortage. | Uses global `qty_available` without warehouse/company context; issued quantity belongs to inventory execution. | Keep requested, available, approved, and shortage concepts in material module; expose calculation hooks; move issue execution fields if needed by inventory module. | Refactor. |
| `material_purchase_requisition/models/purchase_requisition.py` | Purchase requisition header model and workflow actions. | `mail`, purchase order, stock picking, material requisition link. | Creates PRs, approves them, creates RFQs/POs, tracks receipts, posts chatter, schedules activities. | Violates target boundaries by creating RFQs/POs and receipt smart buttons; duplicates workflow/notification logic; approval should use workflow-core approval routes. | Keep PR and PR lines in `ti_purchase_requisition`; move RFQ/PO/receipt logic to `ti_procurement`; call workflow-core approval services. | Refactor / move selected features. |
| `material_purchase_requisition/models/purchase_requisition_line.py` | Purchase requisition line model. | `product.product`. | Captures required, available, shortage, estimated unit and total cost. | Cost source is `standard_price`; shortage availability is global rather than context-aware. | Keep PR line demand/cost estimates; make valuation and vendor pricing extensible for procurement. | Refactor. |
| `material_purchase_requisition/wizard/material_requisition_wizard.py` | Quick material request transient wizard. | `hr.employee`, material requisition model. | Creates draft/submitted MRs from popup lines and defaults department from employee. | Wizard can submit via legacy workflow action; lacks quantity validation beyond line presence. | Keep in material module; call workflow-core-backed MR submit action after migration; add positive quantity validation. | Refactor. |
| `material_purchase_requisition/wizard/material_requisition_wizard.xml` | Legacy wizard XML placeholder. | None in current file. | Empty file. | Unused/duplicate because active wizard view is under `views/wizard_views.xml`. | Remove if still unused after XML audit. | Remove because obsolete. |
| `material_purchase_requisition/views/material_requisition_views.xml` | MR tree/form/search views. | MR fields and button methods. | Shows material workflow, buttons, smart buttons, and chatter. | Exposes buttons for inventory issue and purchase creation in material UI. | Keep material views; move buttons to extension modules or gate them through extension hooks/actions. | Refactor. |
| `material_purchase_requisition/views/purchase_requisition_views.xml` | PR tree/form/search views. | PR fields and button methods. | Shows PR workflow, RFQ creation, purchase orders, receipts, and chatter. | Includes RFQ/PO/receipt concerns outside PR ownership. | Keep PR views; move RFQ/PO/receipt pages and buttons to procurement module inheritance views. | Refactor. |
| `material_purchase_requisition/views/wizard_views.xml` | Quick MR wizard form view. | Wizard transient models. | Lets users enter request details and lines. | No positive quantity UI constraint. | Keep with validation improvements in material module. | Keep/refactor. |
| `material_purchase_requisition/views/actions.xml` | Window actions for MR, PR, and wizard. | View/menu XML IDs and models. | Provides menu actions. | Combined action file spans material and purchase domains. | Split actions into target modules. | Refactor. |
| `material_purchase_requisition/views/menu_views.xml` | Menu hierarchy. | Action XML IDs and security groups. | Provides Material & Purchase Requisition menus. | Combined application menu does not match target modular apps. | Split menus by module and expose dashboard menus later. | Refactor. |
| `material_purchase_requisition/data/sequence.xml` | MR and PR sequence definitions. | `ir.sequence`. | Generates MR and PR document numbers. | Combined file contains multiple domain sequences. | Move MR sequence to material module and PR sequence to purchase module. | Refactor. |
| `material_purchase_requisition/security/security.xml` | Legacy security groups. | `base`, `purchase`. | Defines production supervisor, inventory manager, purchase user, and purchase manager groups. | Duplicates role concepts that may belong in workflow core; lacks record rules. | Reuse `ti_workflow_core` security groups where applicable; define only module-specific groups; add record rules. | Refactor. |
| `material_purchase_requisition/security/ir.model.access.csv` | ACL definitions. | ORM model external IDs and groups. | Grants model access for MR, PR, lines, and wizard. | Broad base-user read access and no record-rule enforcement. | Split ACLs by target module; add record rules for ownership/company visibility. | Refactor. |
| `material_purchase_requisition/static/description/icon.png` | Addon icon. | Odoo app metadata. | Displays module icon. | None architecturally. | Reuse or replace per target module branding. | Keep unchanged. |

## Feature classification

| Feature | Current location | Classification | Target location / service |
| --- | --- | --- | --- |
| MR document numbering | `data/sequence.xml`, `models/material_requisition.py` | Keep unchanged initially | `ti_material_requisition` |
| MR draft/submitted/inventory-review/availability lifecycle | `models/material_requisition.py` | Refactor | `ti_material_requisition` using `ti_workflow_core` transition/log helpers |
| MR chatter posts and activities | `models/material_requisition.py` | Replace with Workflow Core service | `ti_workflow_core` notification/mail/activity helpers |
| Shortage calculation | `models/material_requisition_line.py` | Refactor | `ti_material_requisition` extension hook for context-aware stock availability |
| Stock issue through internal pickings | `models/material_requisition.py` | Move to another module | `ti_inventory_control` |
| Purchase requisition creation from shortages | `models/material_requisition.py` | Replace with extension hook | Hook in `ti_material_requisition`, override in `ti_purchase_requisition` |
| PR document numbering | `data/sequence.xml`, `models/purchase_requisition.py` | Keep unchanged initially | `ti_purchase_requisition` |
| PR approval lifecycle | `models/purchase_requisition.py` | Refactor | `ti_purchase_requisition` using `ti_workflow_core` approval route helpers |
| RFQ/PO generation | `models/purchase_requisition.py` | Move to another module | `ti_procurement` |
| Receipt smart button | `models/purchase_requisition.py` | Move to another module | `ti_procurement` or `ti_inventory_control` depending final receipt ownership |
| Quick MR wizard | `wizard/material_requisition_wizard.py`, `views/wizard_views.xml` | Refactor | `ti_material_requisition` |
| Combined menus/actions | `views/actions.xml`, `views/menu_views.xml` | Refactor | Split by target module |
| Dashboards referenced in manifest description | Manifest only | Move to another module | `ti_management_dashboard` |
| Checked-in Python bytecode | `__pycache__/*.pyc` | Remove because obsolete | Not applicable |

## Migration sequence

1. Establish this migration plan and clean repository artifacts that are not source code.
2. Create `ti_material_requisition` by extracting MR models, MR lines, wizard, MR sequence, material views, and material ACLs.
3. Add material extension hooks: `_get_shortage_lines()`, `_prepare_purchase_requisition_values()`, `_can_create_purchase_requisition()`, and inventory issue delegation points.
4. Replace direct workflow logging/notification/activity behavior with calls to `ti_workflow_core` helpers.
5. Create `ti_purchase_requisition` by extracting PR models, PR lines, PR sequence, PR views, and PR ACLs.
6. Override material purchase-extension hooks in `ti_purchase_requisition` without introducing circular imports.
7. Move stock reservation/issue/return/transfer actions to `ti_inventory_control` via inherited MR methods and views.
8. Move RFQ/PO/vendor/receipt behavior to `ti_procurement` via inherited PR methods and views.
9. Move analytics, delayed requests, shortages dashboard, and executive KPIs to `ti_management_dashboard`.
10. Run install/update validation after each module, and do not proceed to the next module until the current module is approved.

## Current technical debt and validation risks

- The legacy addon combines material, purchase, inventory, procurement, and reporting responsibilities in one installable module.
- Workflow state transitions directly call `write()` and `message_post()` instead of central workflow services.
- Activities are scheduled directly instead of using central notification helpers.
- Stock quantities use `product.qty_available` without explicit warehouse or company context.
- Record rules are absent, while ACLs grant broad base-user read access.
- RFQ and stock picking creation occur in domains that should be owned by future modules.
- Python bytecode files were tracked in Git and should not be versioned.

## Approval gate

This document completes the initial architecture review and module refactoring plan. The next implementation step should be the extraction/refactor of `ti_material_requisition` only. Work on `ti_purchase_requisition`, `ti_inventory_control`, `ti_procurement`, and `ti_management_dashboard` should wait until the material module design is approved.
