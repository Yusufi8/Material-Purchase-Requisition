/** @odoo-module **/

/*
 * Shared bridge to the configurator that already powers Purchase Order
 * Lines.  It deliberately reuses the existing controller, QWeb template,
 * OptionalProductsModal and sale.VariantMixin product resolver.  Host fields
 * only provide their document context and decide what to do on confirmation.
 */
import { OptionalProductsModal } from "@purchase_product_configurator/js/product_configurator";
import {
    selectOrCreateProduct,
    getSelectedVariantValues,
    getNoVariantAttributeValues,
} from "sale.VariantMixin";

export async function openProductConfigurator(host, options) {
    const {
        productTemplateId,
        quantity = 1,
        pricelistId = false,
        variantValueIds = [],
        noVariantValueIds = [],
        customAttributeValues = [],
        mode = "add",
        includeOptionalProducts = false,
        onConfirm,
        onCancel,
    } = options;
    const $modal = $(await host.rpc("/purchase_product_configurator/configure", {
        product_template_id: productTemplateId,
        add_qty: quantity,
        pricelist_id: pricelistId,
        product_template_attribute_value_ids: variantValueIds,
        product_no_variant_attribute_value_ids: noVariantValueIds,
        context: host.context || {},
    }));
    const productSelector = 'input[type="hidden"][name="product_id"], input[type="radio"][name="product_id"]:checked';
    const initialProductId = await selectOrCreateProduct.call(
        host,
        $modal,
        parseInt($modal.find(productSelector).first().val(), 10),
        productTemplateId,
        false,
    );
    $modal.find(productSelector).val(initialProductId);

    const rootProduct = {
        product_id: initialProductId,
        product_template_id: productTemplateId,
        quantity: parseFloat($modal.find('input[name="add_qty"]').val() || quantity || 1),
        variant_values: getSelectedVariantValues($modal),
        product_custom_attribute_values: customAttributeValues,
        no_variant_attribute_values: getNoVariantAttributeValues($modal),
    };
    const dialog = new OptionalProductsModal(null, {
        rootProduct,
        pricelistId,
        okButtonText: host.env._t("Confirm"),
        cancelButtonText: host.env._t("Cancel"),
        title: host.env._t("Configure"),
        context: host.context || {},
        mode,
    });
    let modalEl;
    let confirmed = false;
    dialog.opened(() => {
        modalEl = dialog.el;
        host.ui.activateElement(modalEl);
    });
    dialog.on("confirm", null, async () => {
        confirmed = true;
        const products = await dialog.getAndCreateSelectedProducts();
        const [mainProduct, ...optionalProducts] = products;
        await onConfirm(mainProduct, includeOptionalProducts ? optionalProducts : []);
    });
    dialog.on("closed", null, async () => {
        await new Promise(resolve => setTimeout(resolve, 0));
        if (modalEl) {
            host.ui.deactivateElement(modalEl);
        }
        if (!confirmed && onCancel) {
            await onCancel();
        }
    });
    dialog.open();
}
