import React from 'react';
import { Trash2 } from 'lucide-react';

export function LineItemsTable({ lineItems, editable = false, onItemChange, onDeleteItem }) {
    // Ensure lineItems is always an array
    const safeLineItems = lineItems || [];

    const thStyle = {
        textAlign: 'left',
        padding: editable ? '0 10px' : '12px 0',
        fontSize: '12px',
        fontWeight: 600,
        color: editable ? '#6b7280' : '#374151',
        textTransform: 'uppercase',
        letterSpacing: '0.05em'
    };

    const tdStyle = {
        padding: editable ? '8px' : '16px 0',
        fontSize: '14px',
        color: '#4b5563'
    };

    const inputStyle = {
        padding: '8px 12px',
        borderRadius: '6px',
        border: 'none',
        fontSize: '14px',
        color: '#111827',
        backgroundColor: 'transparent',
        width: '100%',
        boxSizing: 'border-box',
        outline: 'none'
    };

    const totalAmount = safeLineItems.reduce((sum, item) => {
        const amount = typeof item.amount === 'string'
            ? parseFloat(item.amount.replace(/[^0-9.-]+/g, '')) || 0
            : item.amount || 0;
        return sum + amount;
    }, 0);

    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{
                width: '100%',
                borderCollapse: editable ? 'separate' : 'collapse',
                borderSpacing: editable ? '0 8px' : '0'
            }}>
                <thead>
                    <tr style={{ borderBottom: editable ? 'none' : '1px solid #f3f4f6' }}>
                        <th style={thStyle}>Product</th>
                        <th style={thStyle}>Description</th>
                        <th style={{ ...thStyle, textAlign: 'right', width: editable ? '80px' : 'auto' }}>Qty</th>
                        <th style={{ ...thStyle, textAlign: 'right', width: editable ? '100px' : 'auto' }}>
                            {editable ? 'Rate' : 'Price'}
                        </th>
                        <th style={{ ...thStyle, textAlign: 'right', width: editable ? '100px' : 'auto' }}>Amount</th>
                        {editable && <th style={{ width: '40px' }}></th>}
                    </tr>
                </thead>
                <tbody>
                    {safeLineItems.map((item, i) => {
                        const itemId = item.id || i;
                        const productName = item.product_name || item.product || '';
                        const description = item.description || '';
                        const quantity = item.quantity || item.qty || 0;
                        const unitPrice = item.unit_price || item.rate || 0;
                        const amount = item.amount || 0;

                        return (
                            <tr
                                key={itemId}
                                style={{
                                    backgroundColor: editable ? '#f9fafb' : (i % 2 === 0 ? '#ffffff' : '#f9fafb'),
                                    borderBottom: !editable && i < safeLineItems.length - 1 ? '1px solid #f3f4f6' : 'none'
                                }}
                            >
                                <td style={{ ...tdStyle, whiteSpace: 'normal', wordBreak: 'break-word', maxWidth: '300px' }}>
                                    {editable ? (
                                        <input
                                            type="text"
                                            value={productName}
                                            onChange={(e) => onItemChange(itemId, 'product', e.target.value)}
                                            style={inputStyle}
                                        />
                                    ) : (
                                        productName
                                    )}
                                </td>
                                <td style={{ ...tdStyle, whiteSpace: 'normal', wordBreak: 'break-word', maxWidth: '300px' }}>
                                    {editable ? (
                                        <input
                                            type="text"
                                            value={description}
                                            onChange={(e) => onItemChange(itemId, 'description', e.target.value)}
                                            style={inputStyle}
                                        />
                                    ) : (
                                        description
                                    )}
                                </td>
                                <td style={{ ...tdStyle, textAlign: 'right' }}>
                                    {editable ? (
                                        <input
                                            type="number"
                                            value={quantity}
                                            onChange={(e) => onItemChange(itemId, 'qty', e.target.value)}
                                            style={{ ...inputStyle, textAlign: 'center' }}
                                        />
                                    ) : (
                                        quantity
                                    )}
                                </td>
                                <td style={{ ...tdStyle, textAlign: 'right' }}>
                                    {editable ? (
                                        <input
                                            type="number"
                                            value={unitPrice}
                                            onChange={(e) => onItemChange(itemId, 'rate', e.target.value)}
                                            style={inputStyle}
                                        />
                                    ) : (
                                        unitPrice
                                    )}
                                </td>
                                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: editable ? 500 : 600, color: '#111827' }}>
                                    {editable ? (
                                        typeof amount === 'number'
                                            ? `$${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                            : amount
                                    ) : (
                                        amount
                                    )}
                                </td>
                                {editable && (
                                    <td style={{ padding: '8px', textAlign: 'center' }}>
                                        <button
                                            onClick={() => onDeleteItem(itemId)}
                                            style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#ef4444' }}
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                )}
                            </tr>
                        );
                    })}
                </tbody>
                <tfoot>
                    <tr>
                        <td
                            colSpan={editable ? "4" : "4"}
                            style={{
                                ...tdStyle,
                                textAlign: 'right',
                                fontWeight: 600,
                                color: '#111827',
                                paddingTop: '20px',
                                borderTop: editable ? '1px solid #e5e7eb' : 'none'
                            }}
                        >
                            Total Amount:
                        </td>
                        <td
                            style={{
                                ...tdStyle,
                                textAlign: 'right',
                                fontWeight: 700,
                                color: '#111827',
                                fontSize: editable ? '18px' : '16px',
                                paddingTop: '20px',
                                borderTop: editable ? '1px solid #e5e7eb' : 'none'
                            }}
                        >
                            {editable
                                ? `$${totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                : (typeof safeLineItems[0]?.amount === 'string' && safeLineItems[0]?.amount.includes('$'))
                                    ? `$${totalAmount.toFixed(2)}`
                                    : totalAmount
                            }
                        </td>
                        {editable && <td></td>}
                    </tr>
                </tfoot>
            </table>
        </div>
    );
}
