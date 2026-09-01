# Reusable Purchase Product Configurator (Odoo 16)

## Architecture

`purchase_product_configurator` remains the single source of truth for variant
selection.  Its existing `/purchase_product_configurator/configure` endpoint,
QWeb templates, `OptionalProductsModal`, and `sale.VariantMixin` continue to
perform all variant, dynamic-variant, custom-value and no-variant resolution.

`static/src/js/configurator_service.js` is the reusable bridge.  The generic
`product_template_configurator` field widget uses it in editable one2many
rows. A host passes the final `product.product` field and its quantity field;
the widget applies only the confirmed main variant. Purchase retains its
Purchase-specific optional-product line creation logic.

Supported locations:

* Purchase order lines (existing behaviour, including matrix edit routing).
* `mr.request.wizard.line` in TI Material Requisition.
* `mrp.bom.line` through the companion
  `purchase_product_configurator_mrp` addon.

## Installation and upgrade

1. Put the three addon folders in an Odoo addons path:
   `purchase_product_configurator`, `ti_material_requisition`, and
   `purchase_product_configurator_mrp`.
2. Restart Odoo and update the Apps list.
3. Upgrade in dependency order:

```bash
odoo-bin -d <database> -u purchase_product_configurator,ti_material_requisition,purchase_product_configurator_mrp
```

## Test procedure

1. On a Purchase Order, select a configurable template, configure it, and
   verify optional products and matrix editing still operate as before.
2. In **Request Materials**, add a line, select a template, configure its
   attributes, and confirm that **Configured Variant** is the exact variant.
3. On a BOM component row, select a template and confirm that the standard
   `product_id` is the selected variant.
4. Cancel a new configuration and verify no mismatched template/variant is
   left on the row. Change an already configured template and cancel to verify
   that the prior valid values are restored.

The Python constraints reject a product variant that does not belong to the
stored template. The material-request wizard also rejects submission until an
exact product variant exists on every line.
