{
    'name': 'Material & Purchase Requisition',
    'version': '16.0.3.0.0',
    'category': 'Manufacturing',
    'summary': 'Material Requisition and Purchase Requisition Workflow for Manufacturing',
    'description': """
Material & Purchase Requisition Management
==========================================

Fully integrated requisition workflow embedded directly inside
Manufacturing, Inventory, and Purchase — no separate app required.

Manufacturing  (Production Supervisor)
---------------------------------------
- Quick wizard to request materials
- Track status of own requisitions

Inventory  (Inventory Manager)
-------------------------------
- Review incoming material requests
- Check stock availability
- Issue materials via internal transfer
- Raise purchase requisition for shortages

Purchase  (Purchase Team)
---------------------------
- Review and approve purchase requisitions
- Generate RFQ / Purchase Orders
- Mark procurement as done
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
        'mrp',          # REQUIRED: menus now hook into mrp.menu_mrp_root
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/material_requisition_views.xml',
        'views/purchase_requisition_views.xml',
        'views/wizard_views.xml',
        'views/actions.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
}