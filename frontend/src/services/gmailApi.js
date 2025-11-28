/**
 * Gmail API Service
 * Handles Gmail OAuth2 authentication and email syncing
 */

const API_BASE = '/api';

export async function getGmailAuthUrl() {
    const response = await fetch(`${API_BASE}/gmail/authorize`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get Gmail authorization URL');
    }
    return await response.json();
}

export async function saveGmailCredentials(code) {
    const response = await fetch(`${API_BASE}/gmail/oauth/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save Gmail credentials');
    }
    return await response.json();
}

export async function getGmailSettings() {
    const response = await fetch(`${API_BASE}/gmail/settings`);
    if (!response.ok) {
        throw new Error('Failed to fetch Gmail settings');
    }
    return await response.json();
}

export async function saveGmailSettings(settings) {
    const response = await fetch(`${API_BASE}/gmail/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save Gmail settings');
    }
    return await response.json();
}

export async function deleteGmailSettings() {
    const response = await fetch(`${API_BASE}/gmail/settings`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete Gmail settings');
    }
    return await response.json();
}

export async function testGmailConnection() {
    const response = await fetch(`${API_BASE}/gmail/test`, {
        method: 'POST'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Connection test failed');
    }
    return await response.json();
}

export async function syncGmailEmails(startDate = null) {
    const url = startDate 
        ? `${API_BASE}/gmail/sync?start_date=${startDate}`
        : `${API_BASE}/gmail/sync`;
    
    const response = await fetch(url, {
        method: 'POST'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to sync Gmail emails');
    }
    return await response.json();
}

export async function getGmailSyncStatus() {
    const response = await fetch(`${API_BASE}/gmail/sync/status`);
    if (!response.ok) {
        throw new Error('Failed to get Gmail sync status');
    }
    return await response.json();
}

