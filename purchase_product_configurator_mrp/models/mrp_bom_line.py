from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    configurator_product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        help='UI entry point for the shared Purchase Product Configurator.',
    )

    @api.onchange('product_id')
    def _onchange_configurator_product_id(self):
        for line in self:
            if line.product_id:
                line.configurator_product_template_id = line.product_id.product_tmpl_id

    @api.constrains('configurator_product_template_id', 'product_id')
    def _check_configured_product_matches_template(self):
        for line in self:
            if line.configurator_product_template_id and line.product_id and (
                line.configurator_product_template_id != line.product_id.product_tmpl_id
            ):
                raise ValidationError(
                    _('The BOM component variant must belong to its selected product template.')
                )
