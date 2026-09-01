from odoo.tests.common import TransactionCase


class TestMaterialRequestVariantSelection(TransactionCase):
    def test_wizard_line_keeps_template_and_variant_consistent(self):
        template = self.env['product.template'].create({
            'name': 'Configurator integrity product', 'type': 'product',
        })
        variant = template.product_variant_id
        wizard = self.env['mr.request.wizard'].create({
            'department_id': self.env['hr.department'].create({'name': 'Test'}).id,
        })
        line = self.env['mr.request.wizard.line'].create({
            'wizard_id': wizard.id,
            'product_template_id': template.id,
            'product_id': variant.id,
            'qty_requested': 1,
        })
        self.assertEqual(line.product_id.product_tmpl_id, line.product_template_id)
