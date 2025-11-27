/**
 * Settings API Service
 * Handles QuickBooks settings management
 */

const API_BASE = '/api';

export async function getQBSettings() {
    const response = await fetch(`${API_BASE}/settings/quickbooks`);
    if (!response.ok) {
        throw new Error('Failed to fetch QuickBooks settings');
    }
    return await response.json();
}

export async function saveQBSettings(settingsData) {
    const response = await fetch(`${API_BASE}/settings/quickbooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsData)
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save QuickBooks settings');
    }
    return await response.json();
}

export async function deleteQBSettings() {
    const response = await fetch(`${API_BASE}/settings/quickbooks`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete QuickBooks settings');
    }
    return await response.json();
}

export async function testQBConnection() {
    const response = await fetch(`${API_BASE}/settings/quickbooks/test`, {
        method: 'POST'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Connection test failed');
    }
    return await response.json();
}

export async function getInvoiceNumberAttempts() {
    const response = await fetch(`${API_BASE}/settings/invoice-number-attempts`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get invoice number attempts setting');
    }
    return await response.json();
}

export async function saveInvoiceNumberAttempts(maxAttempts) {
    const response = await fetch(`${API_BASE}/settings/invoice-number-attempts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_attempts: maxAttempts })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save invoice number attempts setting');
    }
    return await response.json();
}

