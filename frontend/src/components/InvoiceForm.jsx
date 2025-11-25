import React, { useState, useEffect } from 'react';
import { Plus, Download, Send, FileText } from 'lucide-react';
import { LineItemsTable } from './LineItemsTable';

export function InvoiceForm({ po }) {
    const [invoiceData, setInvoiceData] = useState({
        invoiceNumber: '',
        referencePO: '',
        customerEmail: '',
        invoiceDate: new Date().toISOString().split('T')[0],
        dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        lineItems: [],
        notes: 'Thank you for your business!'
    });

    useEffect(() => {
        if (po) {
            setInvoiceData(prev => ({
                ...prev,
                referencePO: po.po_number || po.filename || '',
                invoiceNumber: `INV-${po.po_number || '001'}`,
                customerEmail: po.customer_email || '',
                lineItems: po.line_items && po.line_items.length > 0 ? po.line_items.map((item, index) => ({
                    id: index + 1,
                    product: item.product_name || '',
                    description: item.description || '',
                    qty: Number(item.quantity) || 0,
                    rate: Number(item.unit_price?.replace(/[^0-9.-]+/g, '')) || 0,
                    amount: Number(item.amount?.replace(/[^0-9.-]+/g, '')) || 0
                })) : [
                    // Fallback mock data if no items extracted
                    { id: 1, product: 'Server Racks', description: '42U server racks with cooling', qty: 3, rate: 2500.00, amount: 7500.00 },
                    { id: 2, product: 'Network Switches', description: '48-port gigabit switches', qty: 6, rate: 800.00, amount: 4800.00 }
                ]
            }));
        }
    }, [po]);

    const handleLineItemChange = (id, field, value) => {
        setInvoiceData(prev => ({
            ...prev,
            lineItems: prev.lineItems.map(item => {
                if (item.id === id) {
                    const updatedItem = { ...item, [field]: value };
                    if (field === 'qty' || field === 'rate') {
                        updatedItem.amount = Number(updatedItem.qty) * Number(updatedItem.rate);
                    }
                    return updatedItem;
                }
                return item;
            })
        }));
    };

    const handleDeleteLineItem = (id) => {
        setInvoiceData(prev => ({
            ...prev,
            lineItems: prev.lineItems.filter(item => item.id !== id)
        }));
    };

    const handleAddLineItem = () => {
        const newId = Math.max(...invoiceData.lineItems.map(i => i.id), 0) + 1;
        setInvoiceData(prev => ({
            ...prev,
            lineItems: [...prev.lineItems, { id: newId, product: '', description: '', qty: 1, rate: 0, amount: 0 }]
        }));
    };

    return (
        <div style={{ padding: '20px', height: '100%', overflowY: 'auto', backgroundColor: '#f9fafb' }}>
            <div style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '20px' }}>Invoice Details</h3>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                    <FormGroup label="Invoice Number">
                        <input
                            type="text"
                            value={invoiceData.invoiceNumber}
                            onChange={(e) => setInvoiceData({ ...invoiceData, invoiceNumber: e.target.value })}
                            style={inputStyle}
                        />
                    </FormGroup>
                    <FormGroup label="Reference PO">
                        <input
                            type="text"
                            value={invoiceData.referencePO}
                            onChange={(e) => setInvoiceData({ ...invoiceData, referencePO: e.target.value })}
                            style={inputStyle}
                        />
                    </FormGroup>
                    <FormGroup label="Customer Email">
                        <input
                            type="email"
                            value={invoiceData.customerEmail}
                            onChange={(e) => setInvoiceData({ ...invoiceData, customerEmail: e.target.value })}
                            style={inputStyle}
                            placeholder="customer@example.com"
                        />
                    </FormGroup>
                    <FormGroup label="Invoice Date">
                        <input
                            type="date"
                            value={invoiceData.invoiceDate}
                            onChange={(e) => setInvoiceData({ ...invoiceData, invoiceDate: e.target.value })}
                            style={inputStyle}
                        />
                    </FormGroup>
                    <FormGroup label="Due Date">
                        <input
                            type="date"
                            value={invoiceData.dueDate}
                            onChange={(e) => setInvoiceData({ ...invoiceData, dueDate: e.target.value })}
                            style={inputStyle}
                        />
                    </FormGroup>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                    <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                        <h4 style={{ fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '8px' }}>Bill To</h4>
                        <div style={{ fontSize: '14px', color: '#111827', fontWeight: 500 }}>
                            {po?.bill_to?.name || 'Unknown'}
                        </div>
                        <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px', whiteSpace: 'pre-line' }}>
                            {po?.bill_to?.address || 'No address available'}
                        </div>
                    </div>

                    <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                        <h4 style={{ fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '8px' }}>Ship To</h4>
                        <div style={{ fontSize: '14px', color: '#111827', fontWeight: 500 }}>
                            {po?.ship_to?.name || 'Unknown'}
                        </div>
                        <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px', whiteSpace: 'pre-line' }}>
                            {po?.ship_to?.address || 'No address available'}
                        </div>
                    </div>
                </div>
            </div>

            <div style={{ marginTop: '20px', backgroundColor: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827' }}>Line Items</h3>
                    <button onClick={handleAddLineItem} style={secondaryButtonStyle}>
                        <Plus size={16} /> Add Item
                    </button>
                </div>

                <LineItemsTable
                    lineItems={invoiceData.lineItems}
                    editable={true}
                    onItemChange={handleLineItemChange}
                    onDeleteItem={handleDeleteLineItem}
                />
            </div>

            <div style={{ marginTop: '20px', backgroundColor: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>Additional Notes</h3>
                <textarea
                    value={invoiceData.notes}
                    onChange={(e) => setInvoiceData({ ...invoiceData, notes: e.target.value })}
                    style={{ ...inputStyle, height: '80px', resize: 'none' }}
                />
            </div>

            <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button style={secondaryButtonStyle}>
                    <Download size={16} /> Download PDF
                </button>
                <button style={secondaryButtonStyle}>
                    <Send size={16} /> Send Email
                </button>
                <button style={primaryButtonStyle}>
                    <FileText size={16} /> Generate Invoice
                </button>
            </div>
        </div>
    );
}

function FormGroup({ label, children }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>{label}</label>
            {children}
        </div>
    );
}

const inputStyle = {
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #e5e7eb',
    fontSize: '14px',
    color: '#111827',
    backgroundColor: '#f3f4f6',
    width: '100%',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.2s'
};

const primaryButtonStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
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
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
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
