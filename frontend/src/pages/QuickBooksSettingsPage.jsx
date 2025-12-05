import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from 'react';
import { Save, Trash2, TestTube, CheckCircle, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { getQBSettings, saveQBSettings, deleteQBSettings, testQBConnection, getInvoiceNumberAttempts, saveInvoiceNumberAttempts } from '../services/settingsApi';

export const QuickBooksSettingsPage = forwardRef(function QuickBooksSettingsPage({ onConnectionCleared, onUnsavedChangesChange }, ref) {
    const [settings, setSettings] = useState({
        client_id: '',
        client_secret: '',
        refresh_token: '',
        realm_id: '',
        environment: 'production'
    });
    const [maxInvoiceAttempts, setMaxInvoiceAttempts] = useState(100);
    const [currentSettings, setCurrentSettings] = useState(null);
    const [savedSettings, setSavedSettings] = useState(null);
    const [savedMaxAttempts, setSavedMaxAttempts] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [savingAttempts, setSavingAttempts] = useState(false);
    const [testing, setTesting] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState(null); // 'success' or 'error'
    const [showPasswords, setShowPasswords] = useState({
        client_id: false,
        client_secret: false,
        refresh_token: false
    });
    const hasUnsavedChangesRef = useRef(false);

    useEffect(() => {
        loadSettings();
        loadInvoiceAttempts();
    }, []);

    const loadSettings = async () => {
        try {
            setLoading(true);
            const data = await getQBSettings();
            setCurrentSettings(data);
            const savedData = {
                client_id: data.client_id || '',
                client_secret: data.client_secret || '',
                refresh_token: data.refresh_token || '',
                environment: data.environment || 'production',
                realm_id: data.realm_id || ''
            };
            setSavedSettings(savedData);
            if (data.configured) {
                // Populate fields with actual saved values for editing
                setSettings(savedData);
            } else {
                // Reset to empty if not configured
                setSettings({
                    client_id: '',
                    client_secret: '',
                    refresh_token: '',
                    realm_id: '',
                    environment: 'production'
                });
            }
            // Reset unsaved changes flag after loading
            hasUnsavedChangesRef.current = false;
            if (onUnsavedChangesChange) {
                onUnsavedChangesChange(false);
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
            setMessage('Failed to load settings');
            setMessageType('error');
        } finally {
            setLoading(false);
        }
    };

    const loadInvoiceAttempts = async () => {
        try {
            const data = await getInvoiceNumberAttempts();
            const attempts = data.max_attempts || 100;
            setMaxInvoiceAttempts(attempts);
            setSavedMaxAttempts(attempts);
        } catch (error) {
            console.error('Failed to load invoice attempts setting:', error);
        }
    };

    const handleSaveAttempts = async () => {
        if (maxInvoiceAttempts <= 0 || !Number.isInteger(maxInvoiceAttempts)) {
            setMessage('Max attempts must be a positive integer');
            setMessageType('error');
            return;
        }

        try {
            setSavingAttempts(true);
            setMessage(null);
            await saveInvoiceNumberAttempts(maxInvoiceAttempts);
            setSavedMaxAttempts(maxInvoiceAttempts);
            setMessage('Invoice number attempts setting saved successfully');
            setMessageType('success');
            checkUnsavedChanges();
        } catch (error) {
            setMessage(error.message || 'Failed to save invoice number attempts setting');
            setMessageType('error');
        } finally {
            setSavingAttempts(false);
        }
    };

    const handleSave = async () => {
        if (!settings.client_id || !settings.client_secret || !settings.refresh_token || !settings.realm_id) {
            setMessage('Please fill in all required fields');
            setMessageType('error');
            return;
        }

        try {
            setSaving(true);
            setMessage(null);
            await saveQBSettings(settings);
            setMessage('QuickBooks settings saved successfully');
            setMessageType('success');
            await loadSettings();
            // After saving, test the connection and clear error if successful
            try {
                const testResult = await testQBConnection();
                if (testResult.success && onConnectionCleared) {
                    onConnectionCleared();
                }
            } catch (testError) {
                // Don't show error if test fails after save - user can test manually
                console.log('Connection test after save failed:', testError);
            }
        } catch (error) {
            setMessage(error.message || 'Failed to save settings');
            setMessageType('error');
        } finally {
            setSaving(false);
        }
    };

    const checkUnsavedChanges = useCallback(() => {
        const hasSettingsChanges = savedSettings && (
            settings.client_id !== savedSettings.client_id ||
            settings.client_secret !== savedSettings.client_secret ||
            settings.refresh_token !== savedSettings.refresh_token ||
            settings.realm_id !== savedSettings.realm_id ||
            settings.environment !== savedSettings.environment
        );
        
        const hasAttemptsChanges = savedMaxAttempts !== null && maxInvoiceAttempts !== savedMaxAttempts;
        
        const hasChanges = hasSettingsChanges || hasAttemptsChanges;
        
        if (hasChanges !== hasUnsavedChangesRef.current) {
            hasUnsavedChangesRef.current = hasChanges;
            if (onUnsavedChangesChange) {
                onUnsavedChangesChange(hasChanges);
            }
        }
        
        return hasChanges;
    }, [settings, maxInvoiceAttempts, savedSettings, savedMaxAttempts, onUnsavedChangesChange]);

    // Check for unsaved changes whenever settings or maxInvoiceAttempts change
    useEffect(() => {
        if (!loading && savedSettings !== null) {
            checkUnsavedChanges();
        }
    }, [checkUnsavedChanges, loading, savedSettings]);

    // Handle browser navigation (beforeunload)
    useEffect(() => {
        const handleBeforeUnload = (e) => {
            if (hasUnsavedChangesRef.current) {
                e.preventDefault();
                e.returnValue = ''; // Chrome requires returnValue to be set
                return ''; // Some browsers require a return value
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    }, []);

    // Expose save method to parent via ref
    useImperativeHandle(ref, () => ({
        save: async () => {
            if (!settings.client_id || !settings.client_secret || !settings.refresh_token || !settings.realm_id) {
                return { success: false, error: 'Please fill in all required fields' };
            }

            try {
                setSaving(true);
                await saveQBSettings(settings);
                await loadSettings();
                // After saving, test the connection and clear error if successful
                try {
                    const testResult = await testQBConnection();
                    if (testResult.success && onConnectionCleared) {
                        onConnectionCleared();
                    }
                } catch (testError) {
                    console.log('Connection test after save failed:', testError);
                }
                return { success: true };
            } catch (error) {
                return { success: false, error: error.message || 'Failed to save settings' };
            } finally {
                setSaving(false);
            }
        }
    }));

    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete QuickBooks settings? This action cannot be undone.')) {
            return;
        }

        try {
            setDeleting(true);
            setMessage(null);
            await deleteQBSettings();
            setMessage('QuickBooks settings deleted successfully');
            setMessageType('success');
            setSettings({
                client_id: '',
                client_secret: '',
                refresh_token: '',
                realm_id: '',
                environment: 'production'
            });
            await loadSettings();
            // Reset unsaved changes after delete
            hasUnsavedChangesRef.current = false;
            if (onUnsavedChangesChange) {
                onUnsavedChangesChange(false);
            }
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
            const result = await testQBConnection();
            if (result.success) {
                setMessage('Connection test successful!');
                setMessageType('success');
                // Clear the connection error banner in App.jsx
                if (onConnectionCleared) {
                    onConnectionCleared();
                }
            } else {
                setMessage(result.message || 'Connection test failed');
                setMessageType('error');
            }
        } catch (error) {
            let errorMessage = error.message || 'Connection test failed';
            
            // Provide helpful guidance for common errors
            if (errorMessage.includes('invalid_grant') || errorMessage.includes('refresh token')) {
                errorMessage = 'Invalid or expired refresh token. Please update your QuickBooks credentials. ' +
                    'You may need to re-authorize your QuickBooks connection in the QuickBooks Developer Portal.';
            } else if (errorMessage.includes('invalid_client') || errorMessage.includes('client_id') || errorMessage.includes('client_secret')) {
                errorMessage = 'Invalid Client ID or Client Secret. Please verify your QuickBooks OAuth credentials.';
            } else if (errorMessage.includes('Missing') || errorMessage.includes('empty')) {
                errorMessage = errorMessage + ' Please fill in all required fields and save your settings.';
            }
            
            setMessage(errorMessage);
            setMessageType('error');
        } finally {
            setTesting(false);
        }
    };

    const togglePasswordVisibility = (field) => {
        setShowPasswords(prev => ({
            ...prev,
            [field]: !prev[field]
        }));
    };

    if (loading) {
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
                    QuickBooks Settings
                </h1>
                <p style={{ fontSize: '14px', color: '#6b7280' }}>
                    Configure your QuickBooks OAuth credentials to enable invoice creation
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
                                    QuickBooks Configured
                                </div>
                                <div style={{ fontSize: '13px', color: '#15803d', marginTop: '2px' }}>
                                    Environment: {currentSettings.environment || 'production'}
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            <AlertCircle size={20} color="#ef4444" />
                            <div style={{ fontSize: '14px', color: '#991b1b' }}>
                                QuickBooks not configured
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
                    alignItems: 'center',
                    gap: '12px'
                }}>
                    {messageType === 'success' ? (
                        <CheckCircle size={20} color="#10b981" />
                    ) : (
                        <AlertCircle size={20} color="#ef4444" />
                    )}
                    <span style={{
                        fontSize: '14px',
                        color: messageType === 'success' ? '#166534' : '#991b1b'
                    }}>
                        {message}
                    </span>
                </div>
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
                                onChange={(e) => setSettings({ ...settings, client_id: e.target.value })}
                                placeholder="Enter QuickBooks Client ID"
                                style={inputStyle}
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
                                onChange={(e) => setSettings({ ...settings, client_secret: e.target.value })}
                                placeholder="Enter QuickBooks Client Secret"
                                style={inputStyle}
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

                    <FormGroup label="Refresh Token" required>
                        <div style={{ position: 'relative' }}>
                            <input
                                type={showPasswords.refresh_token ? 'text' : 'password'}
                                value={settings.refresh_token}
                                onChange={(e) => setSettings({ ...settings, refresh_token: e.target.value })}
                                placeholder="Enter QuickBooks Refresh Token"
                                style={inputStyle}
                            />
                            <button
                                type="button"
                                onClick={() => togglePasswordVisibility('refresh_token')}
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
                                {showPasswords.refresh_token ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </FormGroup>

                    <FormGroup label="Realm ID" required>
                        <input
                            type="text"
                            value={settings.realm_id}
                            onChange={(e) => setSettings({ ...settings, realm_id: e.target.value })}
                            placeholder="Enter QuickBooks Realm ID"
                            style={inputStyle}
                        />
                    </FormGroup>

                    <FormGroup label="Environment">
                        <select
                            value={settings.environment}
                            onChange={(e) => setSettings({ ...settings, environment: e.target.value })}
                            style={inputStyle}
                        >
                            <option value="production">Production</option>
                            <option value="sandbox">Sandbox</option>
                        </select>
                    </FormGroup>
                </div>

                {/* Invoice Number Attempts Setting */}
                <div style={{ 
                    marginTop: '32px', 
                    paddingTop: '32px', 
                    borderTop: '1px solid #e5e7eb' 
                }}>
                    <h3 style={{ 
                        fontSize: '16px', 
                        fontWeight: 600, 
                        color: '#111827', 
                        marginBottom: '16px' 
                    }}>
                        Invoice Number Generation
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <FormGroup label="Max Invoice Number Attempts">
                            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                <input
                                    type="number"
                                    min="1"
                                    value={maxInvoiceAttempts}
                                    onChange={(e) => setMaxInvoiceAttempts(parseInt(e.target.value) || 100)}
                                    placeholder="100"
                                    style={{
                                        ...inputStyle,
                                        width: '150px'
                                    }}
                                />
                                <span style={{ fontSize: '13px', color: '#6b7280' }}>
                                    Maximum number of attempts to find an available invoice number
                                </span>
                                <button
                                    onClick={handleSaveAttempts}
                                    disabled={savingAttempts}
                                    style={{
                                        ...secondaryButtonStyle,
                                        opacity: savingAttempts ? 0.5 : 1,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px',
                                        marginLeft: 'auto'
                                    }}
                                >
                                    {savingAttempts ? (
                                        <>
                                            <div style={{ 
                                                width: '16px', 
                                                height: '16px', 
                                                border: '2px solid rgba(55,65,81,0.3)',
                                                borderTop: '2px solid #374151',
                                                borderRadius: '50%',
                                                animation: 'spin 1s linear infinite'
                                            }}></div>
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            <Save size={14} />
                                            Save
                                        </>
                                    )}
                                </button>
                            </div>
                        </FormGroup>
                    </div>
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px', justifyContent: 'flex-end' }}>
                    {currentSettings?.configured && (
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
                    )}
                    {currentSettings?.configured && (
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
                    )}
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        style={{
                            ...primaryButtonStyle,
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
                                    border: '2px solid rgba(255,255,255,0.3)',
                                    borderTop: '2px solid #fff',
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
});

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

