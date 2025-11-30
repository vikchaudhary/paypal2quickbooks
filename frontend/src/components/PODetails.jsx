import React, { useState, useEffect } from 'react';
import { Building2, Hash, Calendar, User, DollarSign, MapPin, Truck, Mail, Sparkles, Check, X, Tag, FileText } from 'lucide-react';
import { LineItemsTable } from './LineItemsTable';
import { suggestCompanyFromEmail, getInvoiceRecord } from '../services/invoiceApi';

export function PODetails({ po, onExtract, isExtracting, extractedData, onInvoiceSaved }) {
    if (!po) return null;

    // Use extractedData directly, no fallback
    const data = extractedData || {};
    const displayLineItems = data.line_items || [];
    const [suggesting, setSuggesting] = useState(false);
    const [suggestion, setSuggestion] = useState(null);
    const [suggestionError, setSuggestionError] = useState(null);
    const [invoiceRecord, setInvoiceRecord] = useState(null);
    const [loadingInvoiceRecord, setLoadingInvoiceRecord] = useState(false);
    
    // Load invoice record to get accurate status
    useEffect(() => {
        // Reset invoice record when PO changes
        setInvoiceRecord(null);
        setLoadingInvoiceRecord(false);
        
        if (po?.filename) {
            loadInvoiceRecord(po.filename);
        }
    }, [po?.filename]);
    
    
    const loadInvoiceRecord = async (filename) => {
        if (!filename) return;
        
        const currentFilename = po?.filename;
        
        try {
            setLoadingInvoiceRecord(true);
            const result = await getInvoiceRecord(filename);
            // Only set the invoice record if we're still loading for the same filename
            // This prevents race conditions when switching POs quickly
            if (currentFilename === filename) {
                if (result.invoice_record) {
                    setInvoiceRecord(result.invoice_record);
                } else {
                    // Explicitly set to null if no record found
                    setInvoiceRecord(null);
                }
            }
        } catch (error) {
            console.error('Failed to load invoice record:', error);
            // Reset to null on error if still for the same PO
            if (currentFilename === filename) {
                setInvoiceRecord(null);
            }
        } finally {
            if (currentFilename === filename) {
                setLoadingInvoiceRecord(false);
            }
        }
    };
    
    // Get status from invoice record if available, otherwise from PO, otherwise default to "New Order"
    const status = invoiceRecord?.status || po?.status || 'New Order';

    const handleSuggestCompany = async () => {
        if (!data.customer_email || data.customer_email === 'Unknown') {
            return;
        }

        try {
            setSuggesting(true);
            setSuggestionError(null);
            const result = await suggestCompanyFromEmail(data.customer_email);
            setSuggestion(result);
        } catch (error) {
            setSuggestionError(error.message || 'Failed to suggest company name');
        } finally {
            setSuggesting(false);
        }
    };

    const handleAcceptSuggestion = () => {
        if (suggestion && suggestion.suggested_name) {
            // Update the extracted data with the suggested name
            // Note: This would need to be passed back to parent or stored
            // For now, we'll just show it as accepted
            setSuggestion({ ...suggestion, accepted: true });
        }
    };

    const handleRejectSuggestion = () => {
        setSuggestion(null);
    };

    return (
        <div style={{ padding: '24px', height: '100%', overflowY: 'auto' }}>
            {/* Purchase Order Information */}
            <SectionCard title="Purchase Order Information">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                    <div>
                        <InfoItem icon={Building2} label="Customer Name" value={data.vendor_name} />
                        {/* Show suggestion UI if customer name is Unknown but email exists */}
                        {data.vendor_name === 'Unknown' && data.customer_email && data.customer_email !== 'Unknown' && (
                            <div style={{ marginTop: '8px' }}>
                                {!suggestion ? (
                                    <button
                                        onClick={handleSuggestCompany}
                                        disabled={suggesting}
                                        style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: '6px',
                                            padding: '6px 12px',
                                            fontSize: '12px',
                                            backgroundColor: '#f3f4f6',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '6px',
                                            color: '#374151',
                                            cursor: suggesting ? 'not-allowed' : 'pointer',
                                            opacity: suggesting ? 0.6 : 1
                                        }}
                                    >
                                        <Sparkles size={14} />
                                        {suggesting ? 'Suggesting...' : 'Suggest from email'}
                                    </button>
                                ) : (
                                    <div style={{
                                        padding: '8px 12px',
                                        backgroundColor: suggestion.accepted ? '#f0fdf4' : '#fef3c7',
                                        border: `1px solid ${suggestion.accepted ? '#bbf7d0' : '#fde68a'}`,
                                        borderRadius: '6px',
                                        fontSize: '12px'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                            <span style={{ fontWeight: 500, color: suggestion.accepted ? '#166534' : '#92400e' }}>
                                                Suggested: {suggestion.suggested_name}
                                            </span>
                                            {!suggestion.accepted && (
                                                <div style={{ display: 'flex', gap: '4px' }}>
                                                    <button
                                                        onClick={handleAcceptSuggestion}
                                                        style={{
                                                            padding: '2px 6px',
                                                            backgroundColor: '#10b981',
                                                            color: '#fff',
                                                            border: 'none',
                                                            borderRadius: '4px',
                                                            cursor: 'pointer'
                                                        }}
                                                        title="Accept"
                                                    >
                                                        <Check size={12} />
                                                    </button>
                                                    <button
                                                        onClick={handleRejectSuggestion}
                                                        style={{
                                                            padding: '2px 6px',
                                                            backgroundColor: '#ef4444',
                                                            color: '#fff',
                                                            border: 'none',
                                                            borderRadius: '4px',
                                                            cursor: 'pointer'
                                                        }}
                                                        title="Reject"
                                                    >
                                                        <X size={12} />
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                        <div style={{ fontSize: '11px', color: suggestion.accepted ? '#15803d' : '#92400e' }}>
                                            Source: {suggestion.source === 'quickbooks' ? 'QuickBooks' : 'Heuristic'}
                                        </div>
                                    </div>
                                )}
                                {suggestionError && (
                                    <div style={{
                                        marginTop: '4px',
                                        padding: '6px 8px',
                                        backgroundColor: '#fef2f2',
                                        border: '1px solid #fecaca',
                                        borderRadius: '4px',
                                        fontSize: '11px',
                                        color: '#991b1b'
                                    }}>
                                        {suggestionError}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                    <InfoItem icon={Hash} label="PO Number" value={data.po_number} />
                    <InfoItem icon={Tag} label="Status" value={<StatusBadge status={status} />} />
                    <InfoItem icon={Calendar} label="Order Date" value={data.date} />
                    <InfoItem icon={Truck} label="Delivery Date" value={data.delivery_date} />
                    <InfoItem icon={User} label="Ordered By" value={data.ordered_by} />
                    <InfoItem icon={Mail} label="Customer Email" value={data.customer_email} />
                    <InfoItem icon={DollarSign} label="Total Amount" value={data.total_amount} />
                    <InfoItem icon={FileText} label="Source" value={<SourceDisplay source={po?.source} />} />
                </div>
            </SectionCard>

            {/* Addresses */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '24px' }}>
                <SectionCard title="Ship To" icon={Truck}>
                    <div style={{ marginTop: '12px' }}>
                        <div style={{ fontWeight: 600, color: '#111827', marginBottom: '4px' }}>{data.ship_to?.name || 'Unknown'}</div>
                        <div style={{ color: '#6b7280', fontSize: '14px', lineHeight: '1.5' }}>
                            {(data.ship_to?.address || 'Unknown').split('\n').map((line, i) => (
                                <div key={i}>{line}</div>
                            ))}
                        </div>
                    </div>
                </SectionCard>
                <SectionCard title="Bill To" icon={MapPin}>
                    <div style={{ marginTop: '12px' }}>
                        <div style={{ fontWeight: 600, color: '#111827', marginBottom: '4px' }}>{data.bill_to?.name || 'Unknown'}</div>
                        <div style={{ color: '#6b7280', fontSize: '14px', lineHeight: '1.5' }}>
                            {(data.bill_to?.address || 'Unknown').split('\n').map((line, i) => (
                                <div key={i}>{line}</div>
                            ))}
                        </div>
                    </div>
                </SectionCard>
            </div>


            {/* Products */}
            <div style={{ marginTop: '24px', backgroundColor: '#fff', borderRadius: '12px', padding: '24px', border: '1px solid #e5e7eb' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '20px' }}>Products</h3>
                <LineItemsTable lineItems={data.line_items} editable={false} showMatchColumn={false} />
            </div>

            {/* Note */}
            <div style={{ marginTop: '24px', backgroundColor: '#eff6ff', borderRadius: '8px', padding: '16px', border: '1px solid #dbeafe' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#1e40af', lineHeight: '1.5' }}>
                    <strong>Note:</strong> The information displayed here has been extracted from the purchase order document. Please verify all details before converting to an invoice.
                </p>
            </div>
        </div>
    );
}

function SectionCard({ title, icon: Icon, children }) {
    return (
        <div style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '24px', border: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
                {Icon && <Icon size={18} color="#6b7280" />}
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: 0 }}>{title}</h3>
            </div>
            {children}
        </div>
    );
}

function InfoItem({ icon: Icon, label, value }) {
    return (
        <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ marginTop: '2px' }}>
                <Icon size={18} color="#9ca3af" />
            </div>
            <div>
                <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '2px' }}>{label}</div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>{value || '-'}</div>
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
            padding: '4px 10px',
            borderRadius: '12px',
            textTransform: 'capitalize',
            display: 'inline-block'
        }}>
            {status}
        </span>
    );
}

function SourceDisplay({ source }) {
    if (!source) {
        return <span style={{ color: '#6b7280' }}>Unknown</span>;
    }
    
    const formatDate = (dateStr) => {
        if (!dateStr) return 'Unknown';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric' 
            });
        } catch {
            return dateStr;
        }
    };
    
    if (source.source_type === 'email') {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>
                    Email
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    Subject: {source.email_subject || 'No Subject'}
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    Date: {formatDate(source.email_date)}
                </div>
            </div>
        );
    } else if (source.source_type === 'file') {
        return (
            <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>
                File {source.filename || 'Unknown file'}
            </div>
        );
    }
    
    return <span style={{ color: '#6b7280' }}>Unknown</span>;
}
