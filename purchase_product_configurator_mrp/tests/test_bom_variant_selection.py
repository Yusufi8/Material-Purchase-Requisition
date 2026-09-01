from odoo.tests.common import TransactionCase


class TestBomVariantSelection(TransactionCase):
    def test_component_template_matches_selected_variant(self):
        template = self.env['product.template'].create({
            'name': 'BOM configurator integrity product', 'type': 'product',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': template.id,
            'product_qty': 1,
            'type': 'normal',
        })
        component = self.env['mrp.bom.line'].create({
            'bom_id': bom.id,
            'product_id': template.product_variant_id.id,
            'configurator_product_template_id': template.id,
            'product_qty': 1,
        })
        self.assertEqual(component.product_id.product_tmpl_id, component.configurator_product_template_id)
