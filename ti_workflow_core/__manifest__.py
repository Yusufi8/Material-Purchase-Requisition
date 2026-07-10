{
    'name': 'TI Workflow Core',
    'version': '16.0.1.0.0',
    'category': 'Technical',
    'summary': 'Foundation framework: approval engine, audit trail, timeline, '
               'and notification routing for the T&I Projects workflow platform',
    'description': """
TI Workflow Core
================
Foundation module for the T&I Projects Integrated Operations Workflow Platform.
Install this module FIRST. Every other ti_* module depends on it.

Provides
--------
- ti.workflow.log        : immutable audit trail for every workflow transition
- ti.document.timeline    : chronological event timeline per document
- ti.approval.route       : configurable, amount-aware approval routing
                            (director thresholds are data, not hardcoded numbers)
- ti.notification.rule    : configurable email + activity notification rules
- ti.workflow.mixin       : reusable abstract mixin providing traceability
                            fields (Sales Order / Project / Manufacturing Order /
                            Work Order / Cost Centre) and helper methods used by
                            every operational module

Security Groups (9)
--------------------
- Production User / Production Supervisor
- Inventory User / Inventory Manager (Requisition)
- Purchase User (Requisition) / Purchase Manager (Requisition)
- Operations Director / Managing Director
- System Administrator (Requisition)

Notes
-----
Module-specific approval routes and notification rules (e.g. for Material
Requisition or Purchase Requisition states) are NOT loaded by this module —
they are shipped by the modules that define those models
(ti_material_requisition, ti_purchase_requisition), since this module is
installed before those models exist.
    """,
    'author': 'T&I Projects Private Limited',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
        'stock',
        'purchase',
        'mrp',
        'project',
        'account',
        'sale',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/mail_activity_types.xml',
        'views/ti_workflow_log_views.xml',
        'views/ti_document_timeline_views.xml',
        'views/ti_approval_route_views.xml',
        'views/ti_notification_rule_views.xml',
        'views/ti_approval_wizard_views.xml',
        'views/actions.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
