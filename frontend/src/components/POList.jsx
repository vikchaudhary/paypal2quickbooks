import React, { useState, useEffect } from 'react';
import { Search, Filter, ChevronDown, FileText } from 'lucide-react';
import { getInvoiceRecord } from '../services/invoiceApi';

export function POList({ pos, selectedPO, onSelectPO, onOpenFolder }) {
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedStatus, setSelectedStatus] = useState('All Status');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [invoiceRecords, setInvoiceRecords] = useState({}); // Map of filename -> invoice record

    const statuses = ['All Status', 'New Order', 'Invoice Prepared', 'Invoice Sent', 'Invoice Paid'];

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
        const matchesSearch = po.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (po.po_number && po.po_number.toLowerCase().includes(searchTerm.toLowerCase()));

        const matchesStatus = selectedStatus === 'All Status' ||
            (po.status && po.status.toLowerCase() === selectedStatus.toLowerCase());

        return matchesSearch && matchesStatus;
    });

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
                </div>

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

            <div style={{ overflowY: 'auto', flex: 1, padding: '0 12px 20px' }}>
                {filteredPOs.map((po) => (
                    <div
                        key={po.id}
                        onClick={() => onSelectPO(po)}
                        style={{
                            padding: '16px',
                            marginBottom: '8px',
                            borderRadius: '12px',
                            cursor: 'pointer',
                            backgroundColor: selectedPO?.id === po.id ? '#eff6ff' : '#fff',
                            border: selectedPO?.id === po.id ? '1px solid #bfdbfe' : '1px solid #f3f4f6',
                            transition: 'all 0.2s',
                            boxShadow: selectedPO?.id === po.id ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)' : 'none'
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <div>
                                <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>
                                    {po.po_number || po.filename}
                                </div>
                                <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                                    {po.vendor_name || 'Acme Corporation'}
                                </div>
                            </div>
                            <StatusBadge status={po.status || 'Open'} />
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Order Date:</span>
                                <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                                    {po.date || '11/14/2024'}
                                </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Delivery:</span>
                                <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                                    {po.delivery_date || '11/30/2024'}
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
