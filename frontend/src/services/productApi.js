/**
 * Product Matching API Service
 * Handles product matching between PO ProductStrings and QuickBooks SKUs
 */

const API_BASE = '/api';

export async function getQBItems() {
    const response = await fetch(`${API_BASE}/invoices/products/qb-items`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch QuickBooks items');
    }
    return await response.json();
}

export async function matchProducts(productStrings, threshold = 0.6) {
    const response = await fetch(`${API_BASE}/invoices/products/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            product_strings: productStrings,
            threshold: threshold
        })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to match products');
    }
    return await response.json();
}

export async function getProductMappings() {
    const response = await fetch(`${API_BASE}/invoices/products/mappings`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get product mappings');
    }
    return await response.json();
}

export async function setProductMappings(mappings, skuMetadata = null) {
    const response = await fetch(`${API_BASE}/invoices/products/mappings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mappings: mappings,
            sku_metadata: skuMetadata
        })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to set product mappings');
    }
    return await response.json();
}

export async function getProductMapping(productString) {
    const response = await fetch(`${API_BASE}/invoices/products/mappings/${encodeURIComponent(productString)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get product mapping');
    }
    return await response.json();
}

