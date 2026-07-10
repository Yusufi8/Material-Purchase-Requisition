{
    'name': 'TI Purchase Requisition',
    'version': '16.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Procure material shortages raised from Material Requisitions, '
               'with amount-based director approval and RFQ generation',
    'description': """
TI Purchase Requisition
=========================
Takes shortage lines escalated from an approved Material Requisition
through Purchase Manager review, amount-based Director approval
(Operations Director below the threshold, Managing Director at or above
it — configurable in Settings > TI Workflow Settings > Approval Routes,
not hardcoded), RFQ generation, PO confirmation, and receipt tracking.

Depends on ti_workflow_core (audit trail, timeline, notifications,
approval routing) and ti_material_requisition (the source document this
module extends to add the "Request Purchase" action and the Purchase
Requisitions smart button).
    """,
    'author': 'T&I Projects Private Limited',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ti_workflow_core',
        'ti_material_requisition',
        'purchase',
        'stock',
    ],
    'data': [
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/mail_templates.xml',
        'data/approval_routes.xml',
        'data/notification_rules.xml',
        'views/actions.xml',
        'views/purchase_requisition_views.xml',
        'views/material_requisition_ext_views.xml',
        'views/menu_views.xml',
        'report/pr_report_template.xml',
        'report/pr_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
