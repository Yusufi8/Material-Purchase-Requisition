{
    'name': 'TI Material Requisition',
    'version': '16.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Production teams request materials with full audit trail, '
               'director-approved shortage escalation, and inventory issue tracking',
    'description': """
TI Material Requisition
========================
Lets a Production Supervisor request materials in one step, routes the
request through Supervisor approval, Inventory review, and — when a
shortage is found — Director approval, before issue.

Depends on ti_workflow_core for the audit trail, timeline, notification
engine, and approval routing.

Note on Purchase Requisition
-----------------------------
This module intentionally stops at the 'director_approved' state on the
shortage path. It does NOT create Purchase Requisition records and does
NOT know about the purchase.requisition.request model — that would create
a hidden dependency on a module not listed in 'depends'. The
'purchase_requisition_created' state and the actual PR-creation button are
added by ti_purchase_requisition, which depends on this module and extends
material.requisition via _inherit. Install ti_purchase_requisition to
unlock that step.
    """,
    'author': 'T&I Projects Private Limited',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ti_workflow_core',
        'mrp',
        'stock',
        'hr',
        'project',
    ],
    'data': [
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/mail_templates.xml',
        'data/approval_routes.xml',
        'data/notification_rules.xml',
        'views/wizard_views.xml',
        'views/inventory_review_wizard_views.xml',
        'views/actions.xml',
        'views/material_requisition_views.xml',
        'views/menu_views.xml',
        'report/mr_report_template.xml',
        'report/mr_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
