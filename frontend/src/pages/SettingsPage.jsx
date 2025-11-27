import React, { useState } from 'react';
import { Settings as SettingsIcon, ChevronRight, ArrowLeft } from 'lucide-react';
import { QuickBooksSettingsPage } from './QuickBooksSettingsPage';

export function SettingsPage({ onBackToHome }) {
    const [activeSection, setActiveSection] = useState('quickbooks');

    const sections = [
        { id: 'quickbooks', label: 'QuickBooks', icon: SettingsIcon }
    ];

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
                            onClick={onBackToHome}
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
                            onClick={() => setActiveSection(section.id)}
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
                {activeSection === 'quickbooks' && <QuickBooksSettingsPage />}
            </div>
        </div>
    );
}

