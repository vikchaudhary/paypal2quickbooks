/**
 * QuickBooks Customer API Service
 * Handles customer search and retrieval
 */

const API_BASE = '/api';

export async function searchQBCustomers(searchTerm) {
    const response = await fetch(`${API_BASE}/quickbooks/customers/search?q=${encodeURIComponent(searchTerm)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to search customers');
    }
    const data = await response.json();
    return data.customers || [];
}

export async function getQBCustomer(customerId) {
    const response = await fetch(`${API_BASE}/quickbooks/customers/${encodeURIComponent(customerId)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get customer');
    }
    return await response.json();
}

export async function getNextInvoiceNumber(customerId) {
    const response = await fetch(`${API_BASE}/quickbooks/invoices/next-number/${encodeURIComponent(customerId)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get next invoice number');
    }
    return await response.json();
}

