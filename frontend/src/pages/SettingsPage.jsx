import React, { useState, useRef } from 'react';
import { Settings as SettingsIcon, Mail, Package, ChevronRight, ArrowLeft } from 'lucide-react';
import { QuickBooksSettingsPage } from './QuickBooksSettingsPage';
import { GmailSettingsPage } from './GmailSettingsPage';
import { ProductsSettingsPage } from './ProductsSettingsPage';

export function SettingsPage({ onBackToHome, onQbConnectionCleared }) {
    const [activeSection, setActiveSection] = useState('quickbooks');
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [pendingNavigation, setPendingNavigation] = useState(null);
    const qbSettingsPageRef = useRef(null);

    const sections = [
        { id: 'quickbooks', label: 'QuickBooks', icon: SettingsIcon },
        { id: 'gmail', label: 'Gmail', icon: Mail },
        { id: 'products', label: 'Products', icon: Package }
    ];

    const handleSectionChange = (newSection) => {
        if (hasUnsavedChanges && activeSection === 'quickbooks') {
            setPendingNavigation(() => () => setActiveSection(newSection));
            setShowConfirmDialog(true);
        } else {
            setActiveSection(newSection);
        }
    };

    const handleBackToHome = () => {
        if (hasUnsavedChanges && activeSection === 'quickbooks') {
            setPendingNavigation(() => () => {
                if (onBackToHome) {
                    onBackToHome();
                }
            });
            setShowConfirmDialog(true);
        } else {
            if (onBackToHome) {
                onBackToHome();
            }
        }
    };

    const handleConfirmSave = async () => {
        if (qbSettingsPageRef.current) {
            const result = await qbSettingsPageRef.current.save();
            if (result.success) {
                setShowConfirmDialog(false);
                setHasUnsavedChanges(false);
                if (pendingNavigation) {
                    pendingNavigation();
                    setPendingNavigation(null);
                }
            } else {
                alert(result.error || 'Failed to save settings. Please try again.');
            }
        } else {
            // Fallback: just navigate
            setShowConfirmDialog(false);
            if (pendingNavigation) {
                pendingNavigation();
                setPendingNavigation(null);
            }
        }
    };

    const handleConfirmLeave = () => {
        setShowConfirmDialog(false);
        setHasUnsavedChanges(false);
        if (pendingNavigation) {
            pendingNavigation();
            setPendingNavigation(null);
        }
    };

    const handleConfirmCancel = () => {
        setShowConfirmDialog(false);
        setPendingNavigation(null);
    };

    return (
        <div style={{ display: 'flex', height: '100vh', backgroundColor: '#f9fafb' }}>
            {/* Sidebar */}
            <div style={{
                width: '240px',
                backgroundColor: '#fff',
                borderRight: '1px solid #e5e7eb',
                padding: '24px'
            }}>
                <div style={{ marginBottom: '24px' }}>
                    {onBackToHome && (
                        <button
                            onClick={handleBackToHome}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                marginBottom: '16px',
                                padding: '8px 12px',
                                backgroundColor: '#f3f4f6',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                fontSize: '14px',
                                fontWeight: 500,
                                color: '#374151',
                                cursor: 'pointer',
                                transition: 'background-color 0.2s'
                            }}
                            onMouseEnter={(e) => e.target.style.backgroundColor = '#e5e7eb'}
                            onMouseLeave={(e) => e.target.style.backgroundColor = '#f3f4f6'}
                        >
                            <ArrowLeft size={16} />
                            Back to Home
                        </button>
                    )}
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: 0 }}>
                        Settings
                    </h2>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {sections.map((section) => (
                        <button
                            key={section.id}
                            onClick={() => handleSectionChange(section.id)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '12px 16px',
                                borderRadius: '8px',
                                border: 'none',
                                backgroundColor: activeSection === section.id ? '#f3f4f6' : 'transparent',
                                color: activeSection === section.id ? '#111827' : '#6b7280',
                                fontWeight: activeSection === section.id ? 600 : 500,
                                fontSize: '14px',
                                cursor: 'pointer',
                                textAlign: 'left',
                                width: '100%'
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <section.icon size={18} />
                                <span>{section.label}</span>
                            </div>
                            {activeSection === section.id && <ChevronRight size={16} />}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content Area */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
                {activeSection === 'quickbooks' && (
                    <QuickBooksSettingsPage 
                        ref={qbSettingsPageRef}
                        onConnectionCleared={onQbConnectionCleared}
                        onUnsavedChangesChange={setHasUnsavedChanges}
                    />
                )}
                {activeSection === 'gmail' && <GmailSettingsPage />}
                {activeSection === 'products' && <ProductsSettingsPage />}
            </div>

            {/* Confirmation Dialog */}
            {showConfirmDialog && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        backgroundColor: '#fff',
                        borderRadius: '12px',
                        padding: '24px',
                        maxWidth: '400px',
                        width: '90%',
                        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                    }}>
                        <h3 style={{
                            fontSize: '18px',
                            fontWeight: 600,
                            color: '#111827',
                            marginBottom: '12px'
                        }}>
                            Unsaved Changes
                        </h3>
                        <p style={{
                            fontSize: '14px',
                            color: '#6b7280',
                            marginBottom: '24px',
                            lineHeight: '1.5'
                        }}>
                            You have unsaved changes to your QuickBooks settings. What would you like to do?
                        </p>
                        <div style={{
                            display: 'flex',
                            gap: '12px',
                            justifyContent: 'flex-end'
                        }}>
                            <button
                                onClick={handleConfirmCancel}
                                style={{
                                    padding: '8px 16px',
                                    borderRadius: '6px',
                                    border: '1px solid #e5e7eb',
                                    backgroundColor: '#fff',
                                    color: '#374151',
                                    fontSize: '14px',
                                    fontWeight: 500,
                                    cursor: 'pointer'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleConfirmLeave}
                                style={{
                                    padding: '8px 16px',
                                    borderRadius: '6px',
                                    border: '1px solid #e5e7eb',
                                    backgroundColor: '#fff',
                                    color: '#6b7280',
                                    fontSize: '14px',
                                    fontWeight: 500,
                                    cursor: 'pointer'
                                }}
                            >
                                Leave Without Saving
                            </button>
                            <button
                                onClick={handleConfirmSave}
                                style={{
                                    padding: '8px 16px',
                                    borderRadius: '6px',
                                    border: 'none',
                                    backgroundColor: '#0f172a',
                                    color: '#fff',
                                    fontSize: '14px',
                                    fontWeight: 500,
                                    cursor: 'pointer'
                                }}
                            >
                                Save & Continue
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

