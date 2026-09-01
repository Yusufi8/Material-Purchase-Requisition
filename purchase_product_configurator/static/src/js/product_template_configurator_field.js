/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { openProductConfigurator } from "@purchase_product_configurator/js/configurator_service";

/* A generic product.template entry field for editable x2many rows. */
export class ProductTemplateConfiguratorField extends Many2OneField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.ui = useService("ui");
    }

    get productFieldName() {
        return (this.props.options || {}).product_field || "product_id";
    }

    get quantity() {
        const fieldName = (this.props.options || {}).quantity_field || "product_qty";
        return this.props.record.data[fieldName] || 1;
    }

    get context() {
        return this.props.record.getFieldContext
            ? this.props.record.getFieldContext(this.props.name)
            : {};
    }

    async update(value, params = {}) {
        const previousTemplate = this.props.record.data[this.props.name];
        const previousProduct = this.props.record.data[this.productFieldName];
        await super.update(value, params);
        const templateId = Array.isArray(value) ? value[0] : value;
        const previousTemplateId = Array.isArray(previousTemplate) ? previousTemplate[0] : previousTemplate;
        if (!templateId) {
            await this.props.record.update({ [this.productFieldName]: false });
            return;
        }
        if (templateId === previousTemplateId) {
            return;
        }
        // A template change can never retain a product from the old template.
        await this.props.record.update({ [this.productFieldName]: false });
        const result = await this.orm.call("product.template", "get_single_product_variant", [templateId], {
            context: this.context || {},
        });
        if (result && result.product_id && !result.has_optional_products) {
            await this.props.record.update({
                [this.productFieldName]: [result.product_id, result.product_name],
            });
            return;
        }
        await openProductConfigurator(this, {
            productTemplateId: templateId,
            quantity: this.quantity,
            mode: "add",
            // Optional items make sense only on commercial order lines.
            includeOptionalProducts: false,
            onConfirm: async mainProduct => {
                const name = await this.orm.nameGet("product.product", [mainProduct.product_id], {
                    context: this.context || {},
                });
                await this.props.record.update({
                    [this.productFieldName]: name[0],
                    [(this.props.options || {}).quantity_field || "product_qty"]: mainProduct.quantity,
                });
            },
            onCancel: async () => {
                // On a new or changed row, cancellation must not leave a
                // template paired with a stale/empty variant.
                await this.props.record.update({
                    [this.props.name]: previousTemplate || false,
                    [this.productFieldName]: previousProduct || false,
                });
            },
        });
    }
}

ProductTemplateConfiguratorField.template = Many2OneField.template;
ProductTemplateConfiguratorField.props = Many2OneField.props;
ProductTemplateConfiguratorField.extractProps = Many2OneField.extractProps;
registry.category("fields").add("product_template_configurator", ProductTemplateConfiguratorField);
