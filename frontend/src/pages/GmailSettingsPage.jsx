import React, { useState, useEffect } from 'react';
import { Save, Trash2, TestTube, CheckCircle, AlertCircle, Mail, RefreshCw, Eye, EyeOff, Check, X, FileText, Calendar, Paperclip } from 'lucide-react';
import { 
    getGmailSettings, 
    saveGmailSettings, 
    deleteGmailSettings, 
    testGmailConnection,
    getGmailAuthUrl,
    syncGmailEmails,
    getGmailSyncStatus
} from '../services/gmailApi';

export function GmailSettingsPage() {
    const [settings, setSettings] = useState({
        client_id: '',
        client_secret: '',
        redirect_uri: 'http://localhost:5173/gmail/callback',
        starting_date: '',
        forwarding_email: ''
    });
    const [currentSettings, setCurrentSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState(null);
    const [syncStatus, setSyncStatus] = useState(null);
    const [authUrl, setAuthUrl] = useState(null);
    const [showPasswords, setShowPasswords] = useState({
        client_id: false,
        client_secret: false
    });
    const [domainComparison, setDomainComparison] = useState(null);

    useEffect(() => {
        loadSettings();
        loadSyncStatus();
        checkOAuthCallback();
    }, []);

    const checkOAuthCallback = () => {
        // Check if we're returning from OAuth callback
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        if (code) {
            handleOAuthCallback(code);
        }
    };

    const handleOAuthCallback = async (code) => {
        try {
            setLoading(true);
            const { saveGmailCredentials } = await import('../services/gmailApi');
            await saveGmailCredentials(code);
            setMessage('Gmail connected successfully!');
            setMessageType('success');
            // Remove code from URL
            window.history.replaceState({}, document.title, window.location.pathname);
            await loadSettings();
        } catch (error) {
            setMessage(error.message || 'Failed to connect Gmail');
            setMessageType('error');
        } finally {
            setLoading(false);
        }
    };

    const loadSettings = async () => {
        try {
            setLoading(true);
            const data = await getGmailSettings();
            setCurrentSettings(data);
            if (data.configured) {
                // Use placeholder values for saved credentials
                setSettings(prev => ({
                    ...prev,
                    client_id: data.client_id_masked ? '••••••••••••••••' : '',
                    client_secret: data.client_id_masked ? '••••••••••••••••' : '',
                    redirect_uri: data.redirect_uri || 'http://localhost:5173/gmail/callback',
                    starting_date: data.starting_date || '',
                    forwarding_email: data.forwarding_email || ''
                }));
            } else {
                setSettings({
                    client_id: '',
                    client_secret: '',
                    redirect_uri: 'http://localhost:5173/gmail/callback',
                    starting_date: '',
                    forwarding_email: ''
                });
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
            setMessage('Failed to load settings');
            setMessageType('error');
        } finally {
            setLoading(false);
        }
    };

    const loadSyncStatus = async () => {
        try {
            const status = await getGmailSyncStatus();
            if (status && status.last_sync) {
                setSyncStatus(status);
            }
        } catch (error) {
            // Ignore errors for sync status
            console.error('Failed to load sync status:', error);
        }
    };

    const handleConnectGmail = async () => {
        // Check if OAuth credentials are configured
        if (!currentSettings?.configured) {
            setMessage('Please configure Client ID and Client Secret first, then save settings');
            setMessageType('error');
            return;
        }

        try {
            setLoading(true);
            const result = await getGmailAuthUrl();
            setAuthUrl(result.authorization_url);
            // Redirect to Google OAuth
            window.location.href = result.authorization_url;
        } catch (error) {
            setMessage(error.message || 'Failed to get authorization URL');
            setMessageType('error');
            setLoading(false);
        }
    };

    const togglePasswordVisibility = (field) => {
        setShowPasswords(prev => ({
            ...prev,
            [field]: !prev[field]
        }));
    };

    const handleSave = async () => {
        // Check if fields are empty or contain placeholder values
        const hasPlaceholder = settings.client_id === '••••••••••••••••' || 
                              settings.client_secret === '••••••••••••••••';
        
        if (hasPlaceholder && currentSettings?.configured) {
            // If all fields are placeholders, settings are already saved
            setMessage('Settings are already saved. Click on a field to edit.');
            setMessageType('error');
            return;
        }
        
        if (!settings.client_id || !settings.client_secret) {
            setMessage('Please fill in Client ID and Client Secret');
            setMessageType('error');
            return;
        }

        try {
            setSaving(true);
            setMessage(null);
            await saveGmailSettings({
                client_id: settings.client_id,
                client_secret: settings.client_secret,
                redirect_uri: settings.redirect_uri,
                starting_date: settings.starting_date || null,
                forwarding_email: settings.forwarding_email || null
            });
            setMessage('Gmail settings saved successfully');
            setMessageType('success');
            await loadSettings();
        } catch (error) {
            setMessage(error.message || 'Failed to save settings');
            setMessageType('error');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete Gmail settings? This action cannot be undone.')) {
            return;
        }

        try {
            setDeleting(true);
            setMessage(null);
            await deleteGmailSettings();
            setMessage('Gmail settings deleted successfully');
            setMessageType('success');
            setSettings({
                client_id: '',
                client_secret: '',
                redirect_uri: 'http://localhost:5173/gmail/callback',
                starting_date: '',
                forwarding_email: ''
            });
            await loadSettings();
        } catch (error) {
            setMessage(error.message || 'Failed to delete settings');
            setMessageType('error');
        } finally {
            setDeleting(false);
        }
    };

    const handleTest = async () => {
        try {
            setTesting(true);
            setMessage(null);
            const result = await testGmailConnection();
            if (result.success) {
                setMessage(result.message || 'Connection test successful!');
                setMessageType('success');
            } else {
                setMessage(result.message || 'Connection test failed');
                setMessageType('error');
            }
        } catch (error) {
            setMessage(error.message || 'Connection test failed');
            setMessageType('error');
        } finally {
            setTesting(false);
        }
    };

    const handleSync = async () => {
        try {
            setSyncing(true);
            setMessage(null);
            setDomainComparison(null);
            
            // Check QuickBooks connection before syncing
            try {
                const { testQBConnection } = await import('../services/settingsApi');
                await testQBConnection();
            } catch (qbError) {
                setMessage(
                    `QuickBooks connection failed: ${qbError.message}. ` +
                    `Please check your QuickBooks settings and reauthorize if needed.`
                );
                setMessageType('error');
                setSyncing(false);
                return;
            }
            
            const result = await syncGmailEmails(settings.starting_date || null);
            if (result.success) {
                let message = `Sync completed! Processed ${result.emails_processed} emails, ` +
                    `downloaded ${result.pdfs_downloaded} PDFs.`;
                
                // Add debug info if available
                if (result.debug_info) {
                    const skipped = result.debug_info.skipped_reasons || {};
                    const skippedSummary = Object.entries(skipped)
                        .filter(([_, count]) => count > 0)
                        .map(([reason, count]) => `${reason}: ${count}`)
                        .join(', ');
                    
                    if (skippedSummary) {
                        message += `\n\nSkipped: ${skippedSummary}`;
                    }
                    
                    // Add search query if available
                    if (result.debug_info.search_query) {
                        message += `\n\nSearch Query: ${result.debug_info.search_query}`;
                    }
                    
                    // Store domain comparison data
                    if (result.debug_info.email_domains && result.debug_info.qb_customer_domains) {
                        setDomainComparison({
                            emailDomains: result.debug_info.email_domains,
                            qbDomains: result.debug_info.qb_customer_domains,
                            matchingDomains: result.debug_info.matching_domains || []
                        });
                    }
                    
                    // Note: Email debug info is also displayed separately in the UI below
                }
                
                // Log errors to console for debugging, but don't show in message
                if (result.errors && result.errors.length > 0) {
                    console.warn('Sync errors:', result.errors);
                }
                
                setMessage(message);
                setMessageType('success');
            } else {
                let errorMsg = `Sync failed: ${result.errors?.join(', ') || 'Unknown error'}`;
                if (result.debug_info) {
                    errorMsg += `\n\nDebug info: ${JSON.stringify(result.debug_info, null, 2)}`;
                }
                setMessage(errorMsg);
                setMessageType('error');
            }
            // Store debug info in syncStatus for display
            if (result.debug_info) {
                setSyncStatus({
                    last_sync: new Date().toISOString(),
                    emails_processed: result.emails_processed || 0,
                    pdfs_downloaded: result.pdfs_downloaded || 0,
                    errors: result.errors || [],
                    debug_info: result.debug_info
                });
            } else {
                await loadSyncStatus();
            }
        } catch (error) {
            setMessage(error.message || 'Failed to sync emails');
            setMessageType('error');
        } finally {
            setSyncing(false);
        }
    };

    if (loading && !currentSettings) {
        return (
            <div style={{ padding: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ 
                    width: '24px', 
                    height: '24px', 
                    border: '2px solid #e5e7eb',
                    borderTop: '2px solid #6b7280',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                }}></div>
            </div>
        );
    }

    return (
        <div style={{ padding: '40px', maxWidth: '800px' }}>
            <div style={{ marginBottom: '32px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#111827', marginBottom: '8px' }}>
                    Gmail Settings
                </h1>
                <p style={{ fontSize: '14px', color: '#6b7280' }}>
                    Connect your Gmail account to automatically fetch Purchase Orders from emails
                </p>
            </div>

            {/* Status Card */}
            {currentSettings && (
                <div style={{
                    padding: '16px',
                    backgroundColor: currentSettings.configured ? '#f0fdf4' : '#fef2f2',
                    border: `1px solid ${currentSettings.configured ? '#bbf7d0' : '#fecaca'}`,
                    borderRadius: '8px',
                    marginBottom: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px'
                }}>
                    {currentSettings.configured ? (
                        <>
                            <CheckCircle size={20} color="#10b981" />
                            <div>
                                <div style={{ fontSize: '14px', fontWeight: 600, color: '#166534' }}>
                                    Gmail Connected
                                </div>
                                <div style={{ fontSize: '13px', color: '#15803d', marginTop: '2px' }}>
                                    Ready to sync emails
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            <AlertCircle size={20} color="#ef4444" />
                            <div style={{ fontSize: '14px', color: '#991b1b' }}>
                                Gmail not connected
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* Message */}
            {message && (
                <div style={{
                    padding: '16px',
                    backgroundColor: messageType === 'success' ? '#f0fdf4' : '#fef2f2',
                    border: `1px solid ${messageType === 'success' ? '#bbf7d0' : '#fecaca'}`,
                    borderRadius: '8px',
                    marginBottom: '24px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px'
                }}>
                    {messageType === 'success' ? (
                        <CheckCircle size={20} color="#10b981" style={{ marginTop: '2px', flexShrink: 0 }} />
                    ) : (
                        <AlertCircle size={20} color="#ef4444" style={{ marginTop: '2px', flexShrink: 0 }} />
                    )}
                    <div style={{
                        fontSize: '14px',
                        color: messageType === 'success' ? '#166534' : '#991b1b',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        flex: 1
                    }}>
                        {message}
                    </div>
                </div>
            )}

            {/* Email Debug Info */}
            {syncStatus?.debug_info && (
                <>
                    {/* Failed Emails */}
                    {syncStatus.debug_info.email_debug && syncStatus.debug_info.email_debug.length > 0 && (
                        <div style={{
                            backgroundColor: '#fff',
                            borderRadius: '12px',
                            padding: '24px',
                            border: '1px solid #e5e7eb',
                            marginBottom: '24px'
                        }}>
                            <h3 style={{
                                fontSize: '16px',
                                fontWeight: 600,
                                color: '#111827',
                                marginBottom: '16px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}>
                                <AlertCircle size={18} color="#ef4444" />
                                Failed Emails ({syncStatus.debug_info.email_debug.length})
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {syncStatus.debug_info.email_debug.map((email, idx) => (
                                    <EmailDebugBox key={idx} email={email} isSuccess={false} />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Successful Emails */}
                    {syncStatus.debug_info.successful_emails && syncStatus.debug_info.successful_emails.length > 0 && (
                        <div style={{
                            backgroundColor: '#fff',
                            borderRadius: '12px',
                            padding: '24px',
                            border: '1px solid #e5e7eb',
                            marginBottom: '24px'
                        }}>
                            <h3 style={{
                                fontSize: '16px',
                                fontWeight: 600,
                                color: '#111827',
                                marginBottom: '16px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}>
                                <CheckCircle size={18} color="#10b981" />
                                Successfully Processed ({syncStatus.debug_info.successful_emails.length})
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {syncStatus.debug_info.successful_emails.map((email, idx) => (
                                    <EmailDebugBox key={idx} email={email} isSuccess={true} />
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Settings Form */}
            <div style={{
                backgroundColor: '#fff',
                borderRadius: '12px',
                padding: '24px',
                border: '1px solid #e5e7eb'
            }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <FormGroup label="Client ID" required>
                        <div style={{ position: 'relative' }}>
                            <input
                                type={showPasswords.client_id ? 'text' : 'password'}
                                value={settings.client_id}
                                onChange={(e) => {
                                    if (!currentSettings?.configured || e.target.value !== '••••••••••••••••') {
                                        setSettings({ ...settings, client_id: e.target.value });
                                    }
                                }}
                                placeholder={currentSettings?.configured ? "Settings saved (click to edit)" : "Enter Gmail OAuth2 Client ID"}
                                style={{
                                    ...inputStyle,
                                    color: settings.client_id === '••••••••••••••••' ? '#9ca3af' : '#111827',
                                    cursor: settings.client_id === '••••••••••••••••' ? 'pointer' : 'text'
                                }}
                                onClick={() => {
                                    if (settings.client_id === '••••••••••••••••') {
                                        setSettings({ ...settings, client_id: '' });
                                    }
                                }}
                            />
                            <button
                                type="button"
                                onClick={() => togglePasswordVisibility('client_id')}
                                style={{
                                    position: 'absolute',
                                    right: '12px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    border: 'none',
                                    background: 'transparent',
                                    cursor: 'pointer',
                                    color: '#6b7280'
                                }}
                            >
                                {showPasswords.client_id ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </FormGroup>

                    <FormGroup label="Client Secret" required>
                        <div style={{ position: 'relative' }}>
                            <input
                                type={showPasswords.client_secret ? 'text' : 'password'}
                                value={settings.client_secret}
                                onChange={(e) => {
                                    if (!currentSettings?.configured || e.target.value !== '••••••••••••••••') {
                                        setSettings({ ...settings, client_secret: e.target.value });
                                    }
                                }}
                                placeholder={currentSettings?.configured ? "Settings saved (click to edit)" : "Enter Gmail OAuth2 Client Secret"}
                                style={{
                                    ...inputStyle,
                                    color: settings.client_secret === '••••••••••••••••' ? '#9ca3af' : '#111827',
                                    cursor: settings.client_secret === '••••••••••••••••' ? 'pointer' : 'text'
                                }}
                                onClick={() => {
                                    if (settings.client_secret === '••••••••••••••••') {
                                        setSettings({ ...settings, client_secret: '' });
                                    }
                                }}
                            />
                            <button
                                type="button"
                                onClick={() => togglePasswordVisibility('client_secret')}
                                style={{
                                    position: 'absolute',
                                    right: '12px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    border: 'none',
                                    background: 'transparent',
                                    cursor: 'pointer',
                                    color: '#6b7280'
                                }}
                            >
                                {showPasswords.client_secret ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </FormGroup>

                    <FormGroup label="Redirect URI">
                        <input
                            type="text"
                            value={settings.redirect_uri}
                            onChange={(e) => setSettings({ ...settings, redirect_uri: e.target.value })}
                            placeholder="http://localhost:5173/gmail/callback"
                            style={inputStyle}
                        />
                        <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                            OAuth2 redirect URI (must match Google Cloud Console configuration)
                        </p>
                    </FormGroup>

                    <FormGroup label="Starting Date">
                        <input
                            type="date"
                            value={settings.starting_date}
                            onChange={(e) => setSettings({ ...settings, starting_date: e.target.value })}
                            placeholder="YYYY-MM-DD"
                            style={inputStyle}
                        />
                        <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                            Emails from this date onwards will be searched for POs
                        </p>
                    </FormGroup>

                    <FormGroup label="Forwarding Email">
                        <input
                            type="email"
                            value={settings.forwarding_email}
                            onChange={(e) => setSettings({ ...settings, forwarding_email: e.target.value })}
                            placeholder="pashmina@indianbento.com"
                            style={inputStyle}
                        />
                        <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                            Email address that forwards POs (e.g., pashmina@indianbento.com). Leave empty to search all emails with PDF attachments.
                        </p>
                    </FormGroup>
                </div>

                {/* Gmail Connection Status */}
                {currentSettings?.configured && (
                    <div style={{ 
                        marginTop: '24px', 
                        paddingTop: '24px', 
                        borderTop: '1px solid #e5e7eb' 
                    }}>
                        <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '12px' }}>
                            Gmail Connection
                        </h3>
                        {currentSettings?.tokens_configured ? (
                            <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                    <CheckCircle size={18} color="#10b981" />
                                    <span style={{ fontSize: '14px', fontWeight: 500, color: '#166534' }}>
                                        Gmail Connected
                                    </span>
                                </div>
                                <p style={{ fontSize: '13px', color: '#6b7280', marginLeft: '26px' }}>
                                    Your Gmail account is connected and ready to sync.
                                </p>
                            </div>
                        ) : (
                            <div style={{ marginBottom: '16px' }}>
                                <p style={{ fontSize: '13px', color: '#6b7280', marginBottom: '16px' }}>
                                    OAuth credentials are configured. Click the button below to authorize access to your Gmail account.
                                </p>
                                <button
                                    onClick={handleConnectGmail}
                                    disabled={loading}
                                    style={{
                                        ...primaryButtonStyle,
                                        opacity: loading ? 0.5 : 1,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px'
                                    }}
                                >
                                    <Mail size={16} />
                                    Connect to Gmail
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* Domain Comparison */}
                {domainComparison && (
                    <div style={{ 
                        marginTop: '24px', 
                        paddingTop: '24px', 
                        borderTop: '1px solid #e5e7eb' 
                    }}>
                        <h3 style={{ 
                            fontSize: '16px', 
                            fontWeight: 600, 
                            color: '#111827', 
                            marginBottom: '12px' 
                        }}>
                            Domain Comparison
                        </h3>
                        <div style={{ 
                            display: 'grid', 
                            gridTemplateColumns: '1fr 1fr', 
                            gap: '16px',
                            marginBottom: '16px'
                        }}>
                            {/* Email Domains */}
                            <div style={{ 
                                padding: '12px', 
                                backgroundColor: '#f9fafb', 
                                borderRadius: '6px',
                                border: '1px solid #e5e7eb'
                            }}>
                                <div style={{ 
                                    fontSize: '13px', 
                                    fontWeight: 600, 
                                    color: '#374151',
                                    marginBottom: '8px'
                                }}>
                                    Domains in Emails ({Object.keys(domainComparison.emailDomains).length})
                                </div>
                                <div style={{ 
                                    maxHeight: '200px', 
                                    overflowY: 'auto',
                                    fontSize: '12px'
                                }}>
                                    {Object.entries(domainComparison.emailDomains)
                                        .sort((a, b) => b[1] - a[1]) // Sort by count
                                        .map(([domain, count]) => {
                                            const isMatch = domainComparison.matchingDomains.includes(domain);
                                            return (
                                                <div 
                                                    key={domain}
                                                    style={{
                                                        padding: '4px 8px',
                                                        marginBottom: '4px',
                                                        backgroundColor: isMatch ? '#dcfce7' : '#fee2e2',
                                                        border: `1px solid ${isMatch ? '#bbf7d0' : '#fecaca'}`,
                                                        borderRadius: '4px',
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center'
                                                    }}
                                                >
                                                    <span style={{ 
                                                        color: isMatch ? '#166534' : '#991b1b',
                                                        fontWeight: isMatch ? 600 : 400
                                                    }}>
                                                        {domain}
                                                        {isMatch && (
                                                            <span style={{ marginLeft: '6px', fontSize: '10px' }}>✓</span>
                                                        )}
                                                    </span>
                                                    <span style={{ 
                                                        color: isMatch ? '#15803d' : '#dc2626',
                                                        fontSize: '11px',
                                                        fontWeight: 500
                                                    }}>
                                                        {count}
                                                    </span>
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>
                            
                            {/* QuickBooks Domains */}
                            <div style={{ 
                                padding: '12px', 
                                backgroundColor: '#f9fafb', 
                                borderRadius: '6px',
                                border: '1px solid #e5e7eb'
                            }}>
                                <div style={{ 
                                    fontSize: '13px', 
                                    fontWeight: 600, 
                                    color: '#374151',
                                    marginBottom: '8px'
                                }}>
                                    QuickBooks Customer Domains ({domainComparison.qbDomains.length})
                                </div>
                                <div style={{ 
                                    maxHeight: '200px', 
                                    overflowY: 'auto',
                                    fontSize: '12px'
                                }}>
                                    {domainComparison.qbDomains.map((domain) => {
                                        const isMatch = domainComparison.matchingDomains.includes(domain);
                                        const emailCount = domainComparison.emailDomains[domain] || 0;
                                        return (
                                            <div 
                                                key={domain}
                                                style={{
                                                    padding: '4px 8px',
                                                    marginBottom: '4px',
                                                    backgroundColor: isMatch ? '#dcfce7' : '#fff',
                                                    border: `1px solid ${isMatch ? '#bbf7d0' : '#e5e7eb'}`,
                                                    borderRadius: '4px',
                                                    display: 'flex',
                                                    justifyContent: 'space-between',
                                                    alignItems: 'center'
                                                }}
                                            >
                                                <span style={{ 
                                                    color: isMatch ? '#166534' : '#374151',
                                                    fontWeight: isMatch ? 600 : 400
                                                }}>
                                                    {domain}
                                                    {isMatch && (
                                                        <span style={{ marginLeft: '6px', fontSize: '10px' }}>✓</span>
                                                    )}
                                                </span>
                                                {emailCount > 0 && (
                                                    <span style={{ 
                                                        color: '#15803d',
                                                        fontSize: '11px',
                                                        fontWeight: 500
                                                    }}>
                                                        {emailCount} email{emailCount !== 1 ? 's' : ''}
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                        {domainComparison.matchingDomains.length > 0 && (
                            <div style={{ 
                                padding: '12px', 
                                backgroundColor: '#f0fdf4', 
                                borderRadius: '6px',
                                border: '1px solid #bbf7d0',
                                fontSize: '13px',
                                color: '#166534'
                            }}>
                                <strong>Matching domains ({domainComparison.matchingDomains.length}):</strong>{' '}
                                {domainComparison.matchingDomains.join(', ')}
                            </div>
                        )}
                        {domainComparison.matchingDomains.length === 0 && (
                            <div style={{ 
                                padding: '12px', 
                                backgroundColor: '#fef2f2', 
                                borderRadius: '6px',
                                border: '1px solid #fecaca',
                                fontSize: '13px',
                                color: '#991b1b'
                            }}>
                                <strong>No matching domains found.</strong> This is why PDFs are not being downloaded. 
                                Make sure QuickBooks customers have email addresses configured that match the email domains.
                            </div>
                        )}
                    </div>
                )}

                {/* Sync Status */}
                {syncStatus && (
                    <div style={{ 
                        marginTop: '24px', 
                        paddingTop: '24px', 
                        borderTop: '1px solid #e5e7eb' 
                    }}>
                        <h3 style={{ 
                            fontSize: '16px', 
                            fontWeight: 600, 
                            color: '#111827', 
                            marginBottom: '12px' 
                        }}>
                            Last Sync
                        </h3>
                        <div style={{ 
                            padding: '12px', 
                            backgroundColor: '#f9fafb', 
                            borderRadius: '6px',
                            fontSize: '13px',
                            color: '#374151'
                        }}>
                            <div>Date: {new Date(syncStatus.last_sync).toLocaleString()}</div>
                            <div>Emails Processed: {syncStatus.emails_processed || 0}</div>
                            <div>PDFs Downloaded: {syncStatus.pdfs_downloaded || 0}</div>
                            {syncStatus.errors && syncStatus.errors.length > 0 && (
                                <div style={{ color: '#ef4444', marginTop: '8px' }}>
                                    Errors: {syncStatus.errors.length}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                    {currentSettings?.configured && (
                        <>
                            <button
                                onClick={handleSync}
                                disabled={syncing || !settings.starting_date}
                                style={{
                                    ...primaryButtonStyle,
                                    opacity: (syncing || !settings.starting_date) ? 0.5 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                {syncing ? (
                                    <>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            border: '2px solid rgba(255,255,255,0.3)',
                                            borderTop: '2px solid #fff',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }}></div>
                                        Syncing...
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw size={16} />
                                        Sync Emails
                                    </>
                                )}
                            </button>
                            <button
                                onClick={handleTest}
                                disabled={testing}
                                style={{
                                    ...secondaryButtonStyle,
                                    opacity: testing ? 0.5 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                {testing ? (
                                    <>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            border: '2px solid rgba(55,65,81,0.3)',
                                            borderTop: '2px solid #374151',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }}></div>
                                        Testing...
                                    </>
                                ) : (
                                    <>
                                        <TestTube size={16} />
                                        Test Connection
                                    </>
                                )}
                            </button>
                            <button
                                onClick={handleDelete}
                                disabled={deleting}
                                style={{
                                    ...dangerButtonStyle,
                                    opacity: deleting ? 0.5 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                {deleting ? (
                                    <>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            border: '2px solid rgba(239,68,68,0.3)',
                                            borderTop: '2px solid #ef4444',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }}></div>
                                        Deleting...
                                    </>
                                ) : (
                                    <>
                                        <Trash2 size={16} />
                                        Delete
                                    </>
                                )}
                            </button>
                        </>
                    )}
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        style={{
                            ...(currentSettings?.configured ? secondaryButtonStyle : primaryButtonStyle),
                            opacity: saving ? 0.5 : 1,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}
                    >
                        {saving ? (
                            <>
                                <div style={{ 
                                    width: '16px', 
                                    height: '16px', 
                                    border: `2px solid ${currentSettings?.configured ? 'rgba(55,65,81,0.3)' : 'rgba(255,255,255,0.3)'}`,
                                    borderTop: `2px solid ${currentSettings?.configured ? '#374151' : '#fff'}`,
                                    borderRadius: '50%',
                                    animation: 'spin 1s linear infinite'
                                }}></div>
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save size={16} />
                                Save Settings
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}

function FormGroup({ label, required, children }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
                {label} {required && <span style={{ color: '#ef4444' }}>*</span>}
            </label>
            {children}
        </div>
    );
}

const inputStyle = {
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid #e5e7eb',
    fontSize: '14px',
    color: '#111827',
    backgroundColor: '#fff',
    width: '100%',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.2s'
};

const primaryButtonStyle = {
    backgroundColor: '#0f172a',
    color: '#fff',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'background-color 0.2s'
};

const secondaryButtonStyle = {
    backgroundColor: '#fff',
    color: '#374151',
    border: '1px solid #e5e7eb',
    padding: '10px 16px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'background-color 0.2s'
};

const dangerButtonStyle = {
    backgroundColor: '#fff',
    color: '#ef4444',
    border: '1px solid #fecaca',
    padding: '10px 16px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'background-color 0.2s'
};

function EmailDebugBox({ email, isSuccess }) {
    const formatDate = (dateStr) => {
        if (!dateStr) return 'Unknown';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString();
        } catch {
            return dateStr;
        }
    };

    return (
        <div style={{
            padding: '16px',
            backgroundColor: isSuccess ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${isSuccess ? '#bbf7d0' : '#fecaca'}`,
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
        }}>
            {/* Subject */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <FileText size={16} color={isSuccess ? '#15803d' : '#dc2626'} style={{ marginTop: '2px', flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Subject</div>
                    <div style={{ fontSize: '14px', fontWeight: 500, color: isSuccess ? '#166534' : '#991b1b' }}>
                        {email.subject || 'No Subject'}
                    </div>
                </div>
            </div>

            {/* Date */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <Calendar size={16} color={isSuccess ? '#15803d' : '#dc2626'} style={{ marginTop: '2px', flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Date</div>
                    <div style={{ fontSize: '14px', color: isSuccess ? '#166534' : '#991b1b' }}>
                        {formatDate(email.date)}
                    </div>
                </div>
            </div>

            {/* Attachments */}
            {email.attachment_names && email.attachment_names.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <Paperclip size={16} color={isSuccess ? '#15803d' : '#dc2626'} style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Original Attachments</div>
                        <div style={{ fontSize: '14px', color: isSuccess ? '#166534' : '#991b1b' }}>
                            {email.attachment_names.join(', ') || 'None'}
                        </div>
                    </div>
                </div>
            )}

            {/* Original Sender (only for failed emails) */}
            {!isSuccess && email.sender_email && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <Mail size={16} color="#dc2626" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Original Sender</div>
                        <div style={{ fontSize: '14px', color: '#991b1b' }}>
                            {email.sender_email}
                        </div>
                    </div>
                </div>
            )}

            {/* Sender Email (forwarding address, only for failed emails) */}
            {!isSuccess && email.from_header && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <Mail size={16} color="#dc2626" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Sender Email (Forwarder)</div>
                        <div style={{ fontSize: '14px', color: '#991b1b' }}>
                            {email.from_header}
                        </div>
                    </div>
                </div>
            )}

            {/* Forwarded Indicator (only for failed emails) */}
            {!isSuccess && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>Forwarded:</div>
                    {email.has_forwarded_indicators ? (
                        <Check size={16} color="#10b981" />
                    ) : (
                        <X size={16} color="#ef4444" />
                    )}
                </div>
            )}

            {/* Error Message (only for failed emails) */}
            {!isSuccess && email.error && (
                <div style={{
                    padding: '12px',
                    backgroundColor: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderRadius: '6px',
                    marginTop: '4px'
                }}>
                    <div style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: '#991b1b',
                        marginBottom: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                    }}>
                        <AlertCircle size={14} color="#dc2626" />
                        Error/Warning
                    </div>
                    <div style={{
                        fontSize: '13px',
                        color: '#991b1b',
                        lineHeight: '1.5'
                    }}>
                        {email.error}
                    </div>
                </div>
            )}

            {/* Downloaded Files (only for successful emails) */}
            {isSuccess && email.downloaded_filenames && email.downloaded_filenames.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <CheckCircle size={16} color="#10b981" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }}>Downloaded PDFs</div>
                        <div style={{ fontSize: '14px', color: '#166534', fontWeight: 500 }}>
                            {email.downloaded_filenames.join(', ')}
                        </div>
                    </div>
                </div>
            )}

            {/* Email ID (small, at bottom) */}
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '4px' }}>
                Email ID: {email.email_id}
            </div>
        </div>
    );
}

