/**
 * Invoice API Service
 * Handles invoice operations including saving to QuickBooks
 */

const API_BASE = '/api';

export async function saveInvoiceToQB(customerId, invoiceData, poFilename) {
    const response = await fetch(`${API_BASE}/invoices/save-to-quickbooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            customer_id: customerId,
            po_filename: poFilename,
            invoice_data: invoiceData
        })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save invoice to QuickBooks');
    }
    return await response.json();
}

export async function getInvoiceRecord(poFilename) {
    const response = await fetch(`${API_BASE}/invoices/invoice-record/${encodeURIComponent(poFilename)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get invoice record');
    }
    return await response.json();
}

export async function suggestCompanyFromEmail(email) {
    const response = await fetch(`${API_BASE}/invoices/suggest-company-from-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to suggest company name');
    }
    return await response.json();
}

