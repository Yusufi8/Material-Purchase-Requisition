{
    'name': 'Material & Purchase Requisition',
    'version': '16.0.4.0.0',
    'category': 'Manufacturing',
    'summary': 'End-to-end Material & Purchase Requisition workflow for Manufacturing',
    'description': """
Material & Purchase Requisition Management (v4)
=================================================

A full production-to-procurement requisition pipeline, integrated
directly inside Manufacturing, Inventory, and Purchase.

Workflow
--------
draft -> submitted -> supervisor_approved -> inventory_review
      -> stock_reserved -> partial_issue / issued
      -> pr_created -> po_created -> waiting_receipt -> received
      -> closed (or cancelled at any stage)

Highlights
----------
- Linked to Sales Orders, Manufacturing Orders, Work Orders,
  Projects, and Analytic Accounts for full cost/traceability.
- Planning fields: required/planned start/finish dates, priority.
- Independent fulfillment / procurement / production sub-status
  tracking alongside the main workflow state.
- Full approval history: who submitted, approved, reviewed,
  and closed each document, and when.
- Generic, reusable ti.workflow.log audit trail — every state
  transition on Material and Purchase Requisitions is recorded,
  with a read-only "Workflow Logs" register accessible to every
  employee from Manufacturing, Inventory, and Purchase.
- Role-restricted action buttons: Production User, Production
  Supervisor, Inventory Manager, Purchase Manager, and an
  overarching Management role with override permissions on
  otherwise-locked approved documents.
- Dashboard views: Pending Approvals, Material Shortages,
  Open Purchase Requisitions, Delayed Material Requests.
    """,
    'author': 'Yusuf Khan',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'stock',
        'purchase',
        'hr',
        'mrp',
        'sale',
        'project',
        'analytic',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/material_requisition_views.xml',
        'views/purchase_requisition_views.xml',
        'views/wizard_views.xml',
        # 'views/workflow_log_views.xml',
        # 'views/dashboard_views.xml',
        'views/actions.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
