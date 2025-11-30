import React, { useState, useEffect } from 'react';
import { POList } from './components/POList';
import { POMainView } from './components/POMainView';
import { SettingsPage } from './pages/SettingsPage';

function App() {
    const [currentView, setCurrentView] = useState('pos'); // 'pos' or 'settings'
    const [pos, setPos] = useState([]);
    const [selectedPO, setSelectedPO] = useState(null);
    const [isExtracting, setIsExtracting] = useState(false);
    const [extractedData, setExtractedData] = useState(null);

    const [qbConnectionError, setQbConnectionError] = useState(null);
    const [isLoadingPOs, setIsLoadingPOs] = useState(true);
    const [loadingProgress, setLoadingProgress] = useState({
        folderPath: null,
        files: []
    });

    useEffect(() => {
        fetchPOs();
        checkQBConnection();
    }, []);

    // Automatically select the first PO when list is loaded and no PO is selected
    useEffect(() => {
        if (!isLoadingPOs && pos.length > 0 && !selectedPO) {
            handleSelectPO(pos[0]);
        }
    }, [isLoadingPOs, pos, selectedPO]);

    const checkQBConnection = async () => {
        try {
            const response = await fetch('/api/settings/quickbooks/test', {
                method: 'POST'
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'QuickBooks connection failed' }));
                setQbConnectionError(errorData.detail || 'QuickBooks connection failed');
            } else {
                setQbConnectionError(null);
            }
        } catch (error) {
            // Only show error if QB is configured
            try {
                const settingsResponse = await fetch('/api/settings/quickbooks');
                if (settingsResponse.ok) {
                    const settings = await settingsResponse.json();
                    if (settings.configured) {
                        setQbConnectionError('Failed to check QuickBooks connection. Please verify your credentials in Settings.');
                    }
                }
            } catch (e) {
                // Ignore - QB might not be configured yet
            }
        }
    };

    const fetchPOs = async () => {
        setIsLoadingPOs(true);
        setLoadingProgress({ folderPath: null, files: [] });
        
        try {
            // First, get the folder path
            const folderResponse = await fetch('/api/invoices/pos/folder-path');
            let folderPath = null;
            if (folderResponse.ok) {
                const folderData = await folderResponse.json();
                folderPath = folderData.folder_path;
                setLoadingProgress(prev => ({ ...prev, folderPath }));
            }
            
            // Then fetch POs
            const response = await fetch('/api/invoices/pos');
            if (response.ok) {
                const data = await response.json();
                setPos(data);
                
                // Update progress with processed files
                const fileNames = data.map(po => po.filename);
                setLoadingProgress(prev => ({ ...prev, files: fileNames }));
            }
        } catch (error) {
            console.error('Failed to fetch POs:', error);
        } finally {
            setIsLoadingPOs(false);
        }
    };

    const handleSelectPO = (po) => {
        setSelectedPO(po);
        setExtractedData(null); // Reset extracted data when switching POs
        handleExtract(po); // Automatically extract data
    };

    const handleExtract = async (po) => {
        setIsExtracting(true);
        try {
            const response = await fetch(`/api/invoices/pos/${po.filename}/parse`, {
                method: 'POST'
            });
            if (response.ok) {
                const data = await response.json();
                setExtractedData(data);
            }
        } catch (error) {
            console.error('Failed to extract data:', error);
        } finally {
            setIsExtracting(false);
        }
    };

    const handleOpenFolder = () => {
        // Create a hidden file input element
        const input = document.createElement('input');
        input.type = 'file';
        input.webkitdirectory = true;
        input.directory = true;
        input.multiple = true;

        input.onchange = async (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                // Get the folder path from the first file
                // The webkitRelativePath gives us "foldername/filename"
                const firstFile = files[0];
                const relativePath = firstFile.webkitRelativePath;
                const folderName = relativePath.split('/')[0];

                // Construct the full path (this is a limitation - we can only get relative path in browser)
                // We'll need to send the folder name and let backend resolve it
                // For now, we'll extract the common parent path

                // Alternative: Get the path from File API if available
                // Modern browsers don't expose full filesystem paths for security
                // So we'll use a different approach: send files to backend

                // Better approach: Ask user to paste the folder path
                const folderPath = prompt('Please paste the full folder path:', '');

                if (folderPath) {
                    try {
                        const response = await fetch('/api/invoices/pos/set-folder', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_path: folderPath })
                        });

                        if (response.ok) {
                            const data = await response.json();
                            if (data.status === 'success') {
                                // Refresh the PO list
                                await fetchPOs();
                            }
                        }
                    } catch (error) {
                        console.error('Failed to set folder:', error);
                    }
                }
            }
        };

        input.click();
    };


    const handleClosePO = () => {
        setSelectedPO(null);
        setExtractedData(null);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100vh', overflow: 'hidden', backgroundColor: '#f3f4f6' }}>
            {/* Global Header */}
            <div style={{
                height: '60px',
                backgroundColor: '#fff',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '0 24px',
                flexShrink: 0
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                        width: '32px',
                        height: '32px',
                        backgroundColor: '#3b82f6',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff'
                    }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                    </div>
                    <div>
                        <h1 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: 0 }}>PO to Invoice Converter</h1>
                        <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>Manage purchase orders and generate invoices</p>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    {currentView === 'pos' && (
                        <button
                            onClick={handleOpenFolder}
                            style={{
                                backgroundColor: '#0f172a',
                                color: '#fff',
                                border: 'none',
                                padding: '8px 16px',
                                borderRadius: '6px',
                                fontSize: '13px',
                                fontWeight: 500,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                            </svg>
                            Open POs
                        </button>
                    )}
                    <button
                        onClick={() => setCurrentView(currentView === 'settings' ? 'pos' : 'settings')}
                        style={{
                            backgroundColor: currentView === 'settings' ? '#3b82f6' : '#fff',
                            color: currentView === 'settings' ? '#fff' : '#374151',
                            border: '1px solid #e5e7eb',
                            padding: '8px 16px',
                            borderRadius: '6px',
                            fontSize: '13px',
                            fontWeight: 500,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M12 1v6m0 6v6M5.64 5.64l4.24 4.24m4.24 4.24l4.24 4.24M1 12h6m6 0h6M5.64 18.36l4.24-4.24m4.24-4.24l4.24-4.24"></path>
                        </svg>
                        Settings
                    </button>
                </div>
            </div>

            {/* QuickBooks Connection Error Banner */}
            {qbConnectionError && (
                <div style={{
                    backgroundColor: '#fef2f2',
                    borderBottom: '1px solid #fecaca',
                    padding: '12px 24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexShrink: 0
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        <div>
                            <div style={{ fontSize: '14px', fontWeight: 500, color: '#991b1b' }}>
                                QuickBooks Connection Error
                            </div>
                            <div style={{ fontSize: '13px', color: '#dc2626', marginTop: '2px' }}>
                                {qbConnectionError}
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={() => setCurrentView('settings')}
                        style={{
                            backgroundColor: '#dc2626',
                            color: '#fff',
                            border: 'none',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '13px',
                            fontWeight: 500,
                            cursor: 'pointer',
                            marginLeft: '16px'
                        }}
                    >
                        Go to QuickBooks Settings
                    </button>
                </div>
            )}

            {/* Main Content */}
            {currentView === 'settings' ? (
                <SettingsPage 
                    onBackToHome={() => setCurrentView('pos')}
                    onQbConnectionCleared={() => setQbConnectionError(null)}
                />
            ) : (
                <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                    <POList
                        pos={pos}
                        selectedPO={selectedPO}
                        onSelectPO={handleSelectPO}
                        onOpenFolder={handleOpenFolder}
                        onRefreshPOList={fetchPOs}
                    />
                    <POMainView
                        po={selectedPO}
                        onExtract={handleExtract}
                        isExtracting={isExtracting}
                        extractedData={extractedData}
                        onClose={handleClosePO}
                        onRefreshPOList={fetchPOs}
                        isLoadingPOs={isLoadingPOs}
                        loadingProgress={loadingProgress}
                    />
                </div>
            )}
        </div>
    );
}

export default App;
