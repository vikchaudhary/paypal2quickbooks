import React from 'react';
import { Building2, Hash, Calendar, User, DollarSign, MapPin, Truck, Mail } from 'lucide-react';
import { LineItemsTable } from './LineItemsTable';

export function PODetails({ po, onExtract, isExtracting, extractedData }) {
    if (!po) return null;

    // Use extractedData directly, no fallback
    const data = extractedData || {};
    const displayLineItems = data.line_items || [];

    return (
        <div style={{ padding: '24px', height: '100%', overflowY: 'auto' }}>
            {/* Purchase Order Information */}
            <SectionCard title="Purchase Order Information">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                    <InfoItem icon={Building2} label="Customer Name" value={data.vendor_name} />
                    <InfoItem icon={Hash} label="PO Number" value={data.po_number} />
                    <InfoItem icon={Calendar} label="Order Date" value={data.date} />
                    <InfoItem icon={Truck} label="Delivery Date" value={data.delivery_date} />
                    <InfoItem icon={User} label="Ordered By" value={data.ordered_by} />
                    <InfoItem icon={Mail} label="Customer Email" value={data.customer_email} />
                    <InfoItem icon={DollarSign} label="Total Amount" value={data.total_amount} />
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
                <LineItemsTable lineItems={data.line_items} editable={false} />
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
