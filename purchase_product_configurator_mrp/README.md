# Purchase Product Configurator — Manufacturing

This companion addon adds the existing Purchase Product Configurator as the
product-template entry point on Odoo 16 BOM component rows.  The confirmed
value is always stored in the standard `mrp.bom.line.product_id` field.

Install `purchase_product_configurator` first, then install this addon and
upgrade it with `odoo-bin -d <database> -u purchase_product_configurator_mrp`.
