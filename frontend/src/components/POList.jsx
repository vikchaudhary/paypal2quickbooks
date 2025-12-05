import React, { useState, useEffect, useRef } from 'react';
import { Search, Filter, ChevronDown, FileText, RefreshCw, Mail, Trash2 } from 'lucide-react';
import { getInvoiceRecord, markPOAsNotPO } from '../services/invoiceApi';
import { getGmailSettings, syncGmailEmails } from '../services/gmailApi';

export function POList({ pos, selectedPO, onSelectPO, onOpenFolder, onRefreshPOList }) {
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedStatus, setSelectedStatus] = useState('All Status');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [invoiceRecords, setInvoiceRecords] = useState({}); // Map of filename -> invoice record
    const [gmailConfigured, setGmailConfigured] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [syncMessage, setSyncMessage] = useState(null);
    const listRef = useRef(null);

    const statuses = ['All Status', 'New Order', 'Invoice Prepared', 'Invoice Sent', 'Invoice Paid'];

    // Check if Gmail is configured
    useEffect(() => {
        const checkGmailConfig = async () => {
            try {
                const settings = await getGmailSettings();
                setGmailConfigured(settings.configured || false);
            } catch (error) {
                console.error('Failed to check Gmail config:', error);
                setGmailConfigured(false);
            }
        };
        checkGmailConfig();
    }, []);

    // Load invoice records for all POs to get accurate status
    useEffect(() => {
        const loadInvoiceRecords = async () => {
            const records = {};
            const promises = pos.map(async (po) => {
                if (po?.filename) {
                    try {
                        const result = await getInvoiceRecord(po.filename);
                        if (result.invoice_record) {
                            records[po.filename] = result.invoice_record;
                        }
                    } catch (error) {
                        console.error(`Failed to load invoice record for ${po.filename}:`, error);
                    }
                }
            });
            await Promise.all(promises);
            setInvoiceRecords(records);
        };

        if (pos.length > 0) {
            loadInvoiceRecords();
        }
    }, [pos]);

    // Map POs with status from invoice records
    const posWithStatus = pos.map(po => {
        // Get status from invoice record if available, otherwise from PO, otherwise default
        const invoiceRecord = invoiceRecords[po.filename];
        const status = invoiceRecord?.status || po?.status || 'New Order';
        return { ...po, status };
    });

    const filteredPOs = posWithStatus.filter(po => {
        // Filter out POs marked as "Not a PO"
        const invoiceRecord = invoiceRecords[po.filename];
        if (invoiceRecord && invoiceRecord.po_status === 'Not a PO') {
            return false;
        }
        
        const matchesSearch = po.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (po.po_number && po.po_number.toLowerCase().includes(searchTerm.toLowerCase()));

        const matchesStatus = selectedStatus === 'All Status' ||
            (po.status && po.status.toLowerCase() === selectedStatus.toLowerCase());

        return matchesSearch && matchesStatus;
    }).sort((a, b) => {
        // Sort by Order Date (po.date) in descending order (newest first)
        const dateA = parseDateForSort(a.date);
        const dateB = parseDateForSort(b.date);
        
        // If dates are equal, maintain original order
        if (dateA === dateB) return 0;
        
        // Sort descending (newest first)
        return dateB - dateA;
    });

    // Keyboard navigation with arrow keys
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Only handle arrow keys if not typing in an input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                
                if (filteredPOs.length === 0) return;
                
                const currentIndex = filteredPOs.findIndex(po => po.id === selectedPO?.id);
                let newIndex;
                
                if (e.key === 'ArrowDown') {
                    newIndex = currentIndex < filteredPOs.length - 1 ? currentIndex + 1 : 0;
                } else {
                    newIndex = currentIndex > 0 ? currentIndex - 1 : filteredPOs.length - 1;
                }
                
                if (newIndex >= 0 && newIndex < filteredPOs.length) {
                    onSelectPO(filteredPOs[newIndex]);
                    
                    // Scroll the selected PO into view
                    setTimeout(() => {
                        const selectedElement = listRef.current?.querySelector(`[data-po-id="${filteredPOs[newIndex].id}"]`);
                        if (selectedElement) {
                            selectedElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                    }, 0);
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [filteredPOs, selectedPO, onSelectPO]);

    const handleSyncGmail = async () => {
        try {
            setSyncing(true);
            setSyncMessage(null);
            const result = await syncGmailEmails();
            if (result.success) {
                setSyncMessage(
                    `Synced! Processed ${result.emails_processed} emails, ` +
                    `downloaded ${result.pdfs_downloaded} PDFs.`
                );
                // Refresh PO list after successful sync
                if (onRefreshPOList) {
                    setTimeout(() => {
                        onRefreshPOList();
                    }, 1000);
                }
            } else {
                setSyncMessage(`Sync failed: ${result.errors?.join(', ') || 'Unknown error'}`);
            }
        } catch (error) {
            setSyncMessage(`Sync failed: ${error.message}`);
        } finally {
            setSyncing(false);
            // Clear message after 5 seconds
            setTimeout(() => setSyncMessage(null), 5000);
        }
    };

    const handleMarkAsNotPO = async (po, e) => {
        e.stopPropagation(); // Prevent selecting the PO when clicking delete
        
        if (!confirm(`Are you sure you want to hide "${po.filename}"? This will mark it as "Not a PO" and it will be hidden from the list.`)) {
            return;
        }

        try {
            await markPOAsNotPO(po.filename);
            // Refresh the PO list to hide the file
            if (onRefreshPOList) {
                onRefreshPOList();
            }
        } catch (error) {
            alert(`Failed to hide file: ${error.message}`);
        }
    };

    return (
        <div style={{
            width: '380px',
            height: '100vh',
            backgroundColor: '#fff',
            borderRight: '1px solid #e5e7eb',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <div style={{ padding: '24px 20px 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 600, color: '#111827' }}>Purchase Orders</h2>
                    {gmailConfigured && (
                        <button
                            onClick={handleSyncGmail}
                            disabled={syncing}
                            title="Sync Gmail for new POs"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '8px 12px',
                                borderRadius: '6px',
                                border: '1px solid #e5e7eb',
                                backgroundColor: syncing ? '#f3f4f6' : '#fff',
                                color: syncing ? '#9ca3af' : '#374151',
                                fontSize: '13px',
                                fontWeight: 500,
                                cursor: syncing ? 'not-allowed' : 'pointer',
                                transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                                if (!syncing) {
                                    e.target.style.backgroundColor = '#f9fafb';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!syncing) {
                                    e.target.style.backgroundColor = '#fff';
                                }
                            }}
                        >
                            {syncing ? (
                                <>
                                    <div style={{ 
                                        width: '14px', 
                                        height: '14px', 
                                        border: '2px solid #e5e7eb',
                                        borderTop: '2px solid #6b7280',
                                        borderRadius: '50%',
                                        animation: 'spin 1s linear infinite'
                                    }}></div>
                                    Syncing...
                                </>
                            ) : (
                                <>
                                    <Mail size={14} />
                                    Sync Gmail
                                </>
                            )}
                        </button>
                    )}
                </div>
                {syncMessage && (
                    <div style={{
                        padding: '8px 12px',
                        marginBottom: '12px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        backgroundColor: syncMessage.includes('failed') ? '#fef2f2' : '#f0fdf4',
                        color: syncMessage.includes('failed') ? '#991b1b' : '#166534',
                        border: `1px solid ${syncMessage.includes('failed') ? '#fecaca' : '#bbf7d0'}`
                    }}>
                        {syncMessage}
                    </div>
                )}

                <div style={{ display: 'flex', gap: '12px' }}>
                    <div style={{
                        flex: 1,
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center'
                    }}>
                        <Search size={16} color="#9ca3af" style={{ position: 'absolute', left: '12px' }} />
                        <input
                            type="text"
                            placeholder="Search by PO number..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            style={{
                                width: '100%',
                                padding: '10px 12px 10px 36px',
                                borderRadius: '8px',
                                border: '1px solid #f3f4f6',
                                backgroundColor: '#f9fafb',
                                fontSize: '14px',
                                color: '#111827',
                                outline: 'none'
                            }}
                        />
                    </div>
                    <div style={{ position: 'relative' }}>
                        <button
                            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '10px 12px',
                                borderRadius: '8px',
                                border: '1px solid #f3f4f6',
                                backgroundColor: '#f9fafb',
                                color: '#374151',
                                fontSize: '14px',
                                fontWeight: 500,
                                cursor: 'pointer',
                                whiteSpace: 'nowrap'
                            }}
                        >
                            <Filter size={16} />
                            {selectedStatus}
                            <ChevronDown size={14} style={{
                                transform: isDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                                transition: 'transform 0.2s'
                            }} />
                        </button>

                        {isDropdownOpen && (
                            <div style={{
                                position: 'absolute',
                                top: 'calc(100% + 4px)',
                                right: 0,
                                backgroundColor: '#fff',
                                border: '1px solid #e5e7eb',
                                borderRadius: '8px',
                                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                                zIndex: 10,
                                minWidth: '150px',
                                overflow: 'hidden'
                            }}>
                                {statuses.map((status) => (
                                    <div
                                        key={status}
                                        onClick={() => {
                                            setSelectedStatus(status);
                                            setIsDropdownOpen(false);
                                        }}
                                        style={{
                                            padding: '10px 16px',
                                            cursor: 'pointer',
                                            fontSize: '14px',
                                            color: selectedStatus === status ? '#2563eb' : '#374151',
                                            backgroundColor: selectedStatus === status ? '#eff6ff' : '#fff',
                                            fontWeight: selectedStatus === status ? 600 : 400,
                                            transition: 'all 0.15s'
                                        }}
                                        onMouseEnter={(e) => {
                                            if (selectedStatus !== status) {
                                                e.target.style.backgroundColor = '#f9fafb';
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            if (selectedStatus !== status) {
                                                e.target.style.backgroundColor = '#fff';
                                            }
                                        }}
                                    >
                                        {status}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div ref={listRef} style={{ overflowY: 'auto', flex: 1, padding: '0 12px 24px' }}>
                {filteredPOs.map((po) => (
                    <div
                        key={po.id}
                        data-po-id={po.id}
                        onClick={() => onSelectPO(po)}
                        style={{
                            padding: '16px',
                            marginBottom: '8px',
                            borderRadius: '12px',
                            cursor: 'pointer',
                            backgroundColor: selectedPO?.id === po.id ? '#eff6ff' : '#fff',
                            border: selectedPO?.id === po.id ? '1px solid #bfdbfe' : '1px solid #f3f4f6',
                            transition: 'all 0.2s',
                            boxShadow: selectedPO?.id === po.id ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)' : 'none',
                            position: 'relative'
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827', marginBottom: '2px' }}>
                                    {po.vendor_name || 'Acme Corporation'}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                                    <span style={{ fontSize: '11px', color: '#9ca3af' }}>PO#:</span>
                                    <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                                        {po.po_number}
                                    </span>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                                <StatusBadge status={po.status || 'Open'} />
                                <button
                                    onClick={(e) => handleMarkAsNotPO(po, e)}
                                    title="Hide this file (mark as Not a PO)"
                                    style={{
                                        border: 'none',
                                        background: 'transparent',
                                        cursor: 'pointer',
                                        color: '#9ca3af',
                                        padding: '4px',
                                        borderRadius: '4px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        transition: 'all 0.2s'
                                    }}
                                    onMouseEnter={(e) => {
                                        e.target.style.color = '#ef4444';
                                        e.target.style.backgroundColor = '#fef2f2';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.target.style.color = '#9ca3af';
                                        e.target.style.backgroundColor = 'transparent';
                                    }}
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Order Date:</span>
                                <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                                    {formatDate(po.date) || formatDate('11/14/2024')}
                                </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Delivery:</span>
                                <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                                    {formatDate(po.delivery_date) || formatDate('11/30/2024')}
                                </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-end' }}>
                                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Amount:</span>
                                <span style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                                    {po.amount || '$15,750.00'}
                                </span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function parseDateForSort(dateStr) {
    if (!dateStr) return 0; // Treat missing dates as oldest (0)
    
    try {
        let date;
        
        // Check if already in MM/DD/YYYY format
        if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
            const parts = dateStr.split('/');
            const month = parseInt(parts[0], 10);
            const day = parseInt(parts[1], 10);
            const year = parseInt(parts[2], 10);
            date = new Date(year, month - 1, day);
        }
        // Try parsing MM/DD/YYYY or MM-DD-YYYY
        else if (dateStr.includes('/') || dateStr.includes('-')) {
            const parts = dateStr.split(/[\/\-]/);
            if (parts.length === 3) {
                // Assume MM/DD/YYYY or MM-DD-YYYY
                const month = parseInt(parts[0], 10);
                const day = parseInt(parts[1], 10);
                const year = parseInt(parts[2], 10);
                
                // Check if it's a valid date (month <= 12 suggests MM/DD/YYYY)
                if (month <= 12 && day <= 31) {
                    date = new Date(year, month - 1, day);
                } else {
                    // Might be DD/MM/YYYY, try swapping
                    date = new Date(year, day - 1, month);
                }
            }
        }
        
        // Try parsing ISO format (YYYY-MM-DD)
        if (!date || isNaN(date.getTime())) {
            date = new Date(dateStr);
        }
        
        if (isNaN(date.getTime())) {
            return 0; // Treat invalid dates as oldest
        }
        
        // Return timestamp for comparison
        return date.getTime();
    } catch (error) {
        return 0; // Treat errors as oldest
    }
}

function formatDate(dateStr) {
    if (!dateStr) return null;
    
    try {
        // Try parsing various date formats
        let date;
        
        // Check if already in MM/DD/YYYY format
        if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
            return dateStr;
        }
        
        // Try parsing MM/DD/YYYY or MM-DD-YYYY
        if (dateStr.includes('/') || dateStr.includes('-')) {
            const parts = dateStr.split(/[\/\-]/);
            if (parts.length === 3) {
                // Assume MM/DD/YYYY or MM-DD-YYYY
                const month = parseInt(parts[0], 10);
                const day = parseInt(parts[1], 10);
                const year = parseInt(parts[2], 10);
                
                // Check if it's a valid date (month <= 12 suggests MM/DD/YYYY)
                if (month <= 12 && day <= 31) {
                    date = new Date(year, month - 1, day);
                } else {
                    // Might be DD/MM/YYYY, try swapping
                    date = new Date(year, day - 1, month);
                }
            }
        }
        
        // Try parsing ISO format (YYYY-MM-DD)
        if (!date || isNaN(date.getTime())) {
            date = new Date(dateStr);
        }
        
        if (isNaN(date.getTime())) {
            return dateStr; // Return original if can't parse
        }
        
        // Format as MM/DD/YYYY
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const year = date.getFullYear();
        
        return `${month}/${day}/${year}`;
    } catch (error) {
        return dateStr; // Return original if error
    }
}

function StatusBadge({ status }) {
    const getStatusColor = (s) => {
        const normalized = s.toLowerCase();
        switch (normalized) {
            case 'new order': return { bg: '#fee2e2', text: '#991b1b' }; // Red
            case 'invoice prepared': return { bg: '#fef3c7', text: '#92400e' }; // Yellow
            case 'invoice sent': return { bg: '#dbeafe', text: '#1e40af' }; // Blue
            case 'invoice paid': return { bg: '#dcfce7', text: '#166534' }; // Green
            default: return { bg: '#fee2e2', text: '#991b1b' }; // Default to red (New Order)
        }
    };

    const { bg, text } = getStatusColor(status);

    return (
        <span style={{
            backgroundColor: bg,
            color: text,
            fontSize: '11px',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: '12px',
            textTransform: 'capitalize'
        }}>
            {status}
        </span>
    );
}
