{
    'name': 'TI Inventory Control',
    'version': '16.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Partial material issuance, returns to stock, and fulfilment '
               'tracking for Material Requisitions',
    'description': """
TI Inventory Control
======================
ti_material_requisition already implements full-quantity stock reservation
and issue directly (action_reserve_stock / action_issue_materials), so an
MR is fully usable standalone without this module — same principle
ti_material_requisition itself follows with respect to
ti_purchase_requisition.

This module adds what that standalone flow does not cover:

- Partial issue: issue less than the full approved quantity on a line,
  across one or more separate transfers, via ti.issue.materials.wizard.
- Returns: send previously issued materials back to stock via
  ti.stock.return.wizard, decrementing qty_issued accordingly.
- Fulfilment tracking fields on material.requisition (total requested /
  approved / issued / pending quantity, fulfilment rate, fully-issued flag)
  for the dashboards built in ti_management_dashboard.

Depends on ti_workflow_core (audit trail, timeline) and
ti_material_requisition (the model this module extends).
    """,
    'author': 'T&I Projects Private Limited',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ti_workflow_core',
        'ti_material_requisition',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wizard_views.xml',
        'views/actions.xml',
        'views/material_requisition_ext_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
