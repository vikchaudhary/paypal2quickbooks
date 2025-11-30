import React, { useState, useEffect } from 'react';
import { Package, Plus, X, Search, AlertCircle } from 'lucide-react';

const API_BASE = '/api';

export function ProductsSettingsPage() {
    const [skus, setSkus] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [expandedSku, setExpandedSku] = useState(null);
    const [newProductString, setNewProductString] = useState({});
    const [saving, setSaving] = useState({});
    const [refreshing, setRefreshing] = useState(false);
    const [clearing, setClearing] = useState(false);

    useEffect(() => {
        loadSkus();
    }, []);

    const loadSkus = async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await fetch(`${API_BASE}/invoices/products/skus`);
            if (!response.ok) {
                throw new Error('Failed to load SKUs');
            }
            const data = await response.json();
            setSkus(data.skus || []);
        } catch (err) {
            setError(err.message);
            console.error('Failed to load SKUs:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAddProductString = async (sku) => {
        const productString = newProductString[sku]?.trim();
        if (!productString) {
            return;
        }

        try {
            setSaving({ ...saving, [sku]: true });
            const response = await fetch(`${API_BASE}/invoices/products/skus/${encodeURIComponent(sku)}/product-strings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_string: productString })
            });

            if (!response.ok) {
                throw new Error('Failed to add product string');
            }

            // Clear input and reload
            setNewProductString({ ...newProductString, [sku]: '' });
            await loadSkus();
        } catch (err) {
            console.error('Failed to add product string:', err);
            alert(`Failed to add product string: ${err.message}`);
        } finally {
            setSaving({ ...saving, [sku]: false });
        }
    };

    const handleRemoveProductString = async (sku, productString) => {
        if (!confirm(`Remove "${productString}" from ${sku}?`)) {
            return;
        }

        try {
            const response = await fetch(
                `${API_BASE}/invoices/products/skus/${encodeURIComponent(sku)}/product-strings/${encodeURIComponent(productString)}`,
                { method: 'DELETE' }
            );

            if (!response.ok) {
                throw new Error('Failed to remove product string');
            }

            await loadSkus();
        } catch (err) {
            console.error('Failed to remove product string:', err);
            alert(`Failed to remove product string: ${err.message}`);
        }
    };

    const handleRefreshSkus = async () => {
        if (!confirm('This will delete all current SKU mappings and reimport from QuickBooks. Existing ProductString mappings will be preserved if the SKU still exists. Continue?')) {
            return;
        }

        try {
            setRefreshing(true);
            setError(null);
            const response = await fetch(`${API_BASE}/invoices/products/refresh`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to refresh SKUs');
            }

            const data = await response.json();
            await loadSkus();
            
            let message = `Successfully refreshed products. ${data.skus_imported} products imported from QuickBooks.`;
            if (data.total_items !== undefined) {
                message += `\nTotal items fetched: ${data.total_items}`;
            }
            alert(message);
        } catch (err) {
            setError(err.message);
            console.error('Failed to refresh SKUs:', err);
            alert(`Failed to refresh SKUs: ${err.message}`);
        } finally {
            setRefreshing(false);
        }
    };

    const handleClearAll = async () => {
        if (!confirm('This will delete ALL product mappings and SKU data. This action cannot be undone. Continue?')) {
            return;
        }

        try {
            setClearing(true);
            setError(null);
            const response = await fetch(`${API_BASE}/invoices/products/clear`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to clear mappings');
            }

            await loadSkus();
            alert('All mappings cleared successfully.');
        } catch (err) {
            setError(err.message);
            console.error('Failed to clear mappings:', err);
            alert(`Failed to clear mappings: ${err.message}`);
        } finally {
            setClearing(false);
        }
    };

    const filteredSkus = skus.filter(sku => {
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase();
        return (
            (sku.sku && sku.sku.toLowerCase().includes(term)) ||
            (sku.name && sku.name.toLowerCase().includes(term)) ||
            (sku.description && sku.description && sku.description.toLowerCase().includes(term)) ||
            (sku.type && sku.type.toLowerCase().includes(term)) ||
            (sku.id && sku.id.toLowerCase().includes(term)) ||
            sku.product_strings.some(ps => ps.toLowerCase().includes(term))
        );
    });

    if (loading) {
        return (
            <div style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>
                <div style={{ 
                    width: '24px', 
                    height: '24px', 
                    border: '2px solid #e5e7eb',
                    borderTop: '2px solid #6b7280',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                    margin: '0 auto 16px'
                }}></div>
                <p>Loading products...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: '40px', textAlign: 'center' }}>
                <AlertCircle size={24} color="#ef4444" style={{ marginBottom: '12px' }} />
                <p style={{ color: '#ef4444', marginBottom: '16px' }}>Error: {error}</p>
                <button
                    onClick={loadSkus}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: '#0f172a',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px'
                    }}
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#111827', marginBottom: '8px' }}>
                        Products Database
                    </h2>
                    <p style={{ fontSize: '14px', color: '#6b7280' }}>
                        Manage SKUs from QuickBooks and their ProductString mappings (1:many relationship)
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                        onClick={handleRefreshSkus}
                        disabled={refreshing || clearing}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '10px 16px',
                            backgroundColor: '#0f172a',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '14px',
                            fontWeight: 500,
                            cursor: (refreshing || clearing) ? 'not-allowed' : 'pointer',
                            opacity: (refreshing || clearing) ? 0.5 : 1,
                            transition: 'opacity 0.2s'
                        }}
                    >
                        {refreshing ? (
                            <>
                                <div style={{ 
                                    width: '14px', 
                                    height: '14px', 
                                    border: '2px solid rgba(255,255,255,0.3)',
                                    borderTop: '2px solid #fff',
                                    borderRadius: '50%',
                                    animation: 'spin 1s linear infinite'
                                }}></div>
                                Refreshing...
                            </>
                        ) : (
                            <>
                                <Package size={16} />
                                Refresh from QuickBooks
                            </>
                        )}
                    </button>
                    <button
                        onClick={handleClearAll}
                        disabled={refreshing || clearing}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '10px 16px',
                            backgroundColor: '#ef4444',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '14px',
                            fontWeight: 500,
                            cursor: (refreshing || clearing) ? 'not-allowed' : 'pointer',
                            opacity: (refreshing || clearing) ? 0.5 : 1,
                            transition: 'opacity 0.2s'
                        }}
                    >
                        {clearing ? (
                            <>
                                <div style={{ 
                                    width: '14px', 
                                    height: '14px', 
                                    border: '2px solid rgba(255,255,255,0.3)',
                                    borderTop: '2px solid #fff',
                                    borderRadius: '50%',
                                    animation: 'spin 1s linear infinite'
                                }}></div>
                                Clearing...
                            </>
                        ) : (
                            <>
                                <X size={16} />
                                Clear All
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Search */}
            <div style={{ marginBottom: '24px', position: 'relative' }}>
                <Search size={18} style={{ 
                    position: 'absolute', 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    color: '#9ca3af'
                }} />
                <input
                    type="text"
                    placeholder="Search by SKU, Id, Name, Type, Description, or ProductString..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{
                        width: '100%',
                        padding: '10px 12px 10px 40px',
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb',
                        fontSize: '14px',
                        outline: 'none',
                        transition: 'border-color 0.2s'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#0f172a'}
                    onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
                />
            </div>

            {/* SKUs List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {filteredSkus.length === 0 ? (
                    <div style={{ 
                        padding: '40px', 
                        textAlign: 'center', 
                        backgroundColor: '#fff',
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb'
                    }}>
                        <Package size={32} color="#9ca3af" style={{ marginBottom: '12px' }} />
                        <p style={{ color: '#6b7280', fontSize: '14px' }}>
                            {searchTerm ? 'No SKUs found matching your search' : 'No SKUs found'}
                        </p>
                    </div>
                ) : (
                    filteredSkus.map((sku) => (
                        <div
                            key={sku.sku}
                            style={{
                                backgroundColor: '#fff',
                                borderRadius: '8px',
                                border: '1px solid #e5e7eb',
                                overflow: 'hidden'
                            }}
                        >
                            {/* SKU Header */}
                            <div
                                style={{
                                    padding: '16px 20px',
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    justifyContent: 'space-between',
                                    cursor: 'pointer',
                                    backgroundColor: expandedSku === sku.sku ? '#f9fafb' : '#fff',
                                    transition: 'background-color 0.2s'
                                }}
                                onClick={() => setExpandedSku(expandedSku === sku.sku ? null : sku.sku)}
                            >
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                                        <Package size={18} color="#6b7280" />
                                        <span style={{ fontSize: '16px', fontWeight: 600, color: '#111827' }}>
                                            {sku.name || sku.sku}
                                        </span>
                                        {sku.product_strings.length > 0 && (
                                            <span style={{
                                                fontSize: '12px',
                                                padding: '2px 8px',
                                                backgroundColor: '#dbeafe',
                                                color: '#1e40af',
                                                borderRadius: '12px',
                                                fontWeight: 500
                                            }}>
                                                {sku.product_strings.length} mapping{sku.product_strings.length !== 1 ? 's' : ''}
                                            </span>
                                        )}
                                    </div>
                                    <div style={{ marginLeft: '30px', fontSize: '13px', color: '#6b7280', display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px' }}>
                                        <div>
                                            <span style={{ fontWeight: 600, color: '#374151' }}>SKU:</span>
                                        </div>
                                        <div>
                                            <span style={{ fontFamily: 'monospace', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>
                                                {sku.sku}
                                            </span>
                                        </div>
                                        
                                        <div>
                                            <span style={{ fontWeight: 600, color: '#374151' }}>Id:</span>
                                        </div>
                                        <div>
                                            <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                                                {sku.id || 'N/A'}
                                            </span>
                                        </div>
                                        
                                        <div>
                                            <span style={{ fontWeight: 600, color: '#374151' }}>Name:</span>
                                        </div>
                                        <div>
                                            {sku.name || 'N/A'}
                                        </div>
                                        
                                        {sku.description && (
                                            <>
                                                <div>
                                                    <span style={{ fontWeight: 600, color: '#374151' }}>Description:</span>
                                                </div>
                                                <div>
                                                    {sku.description}
                                                </div>
                                            </>
                                        )}
                                        
                                        {sku.type && (
                                            <>
                                                <div>
                                                    <span style={{ fontWeight: 600, color: '#374151' }}>Type:</span>
                                                </div>
                                                <div>
                                                    <span style={{ 
                                                        padding: '2px 8px', 
                                                        backgroundColor: '#e0e7ff', 
                                                        color: '#3730a3',
                                                        borderRadius: '4px',
                                                        fontSize: '12px',
                                                        fontWeight: 500
                                                    }}>
                                                        {sku.type}
                                                    </span>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                                <div style={{ fontSize: '12px', color: '#9ca3af', marginLeft: '16px' }}>
                                    {expandedSku === sku.sku ? '▼' : '▶'}
                                </div>
                            </div>

                            {/* Expanded Content */}
                            {expandedSku === sku.sku && (
                                <div style={{ 
                                    padding: '20px',
                                    borderTop: '1px solid #e5e7eb',
                                    backgroundColor: '#f9fafb'
                                }}>
                                    {/* Product Strings List */}
                                    <div style={{ marginBottom: '20px' }}>
                                        <h4 style={{ 
                                            fontSize: '14px', 
                                            fontWeight: 600, 
                                            color: '#374151',
                                            marginBottom: '12px'
                                        }}>
                                            Mapped ProductStrings (from POs):
                                        </h4>
                                        {sku.product_strings.length === 0 ? (
                                            <p style={{ 
                                                fontSize: '13px', 
                                                color: '#9ca3af',
                                                fontStyle: 'italic',
                                                padding: '12px',
                                                backgroundColor: '#fff',
                                                borderRadius: '6px',
                                                border: '1px dashed #e5e7eb'
                                            }}>
                                                No ProductStrings mapped to this SKU
                                            </p>
                                        ) : (
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                                {sku.product_strings.map((ps) => (
                                                    <div
                                                        key={ps}
                                                        style={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'space-between',
                                                            padding: '10px 12px',
                                                            backgroundColor: '#fff',
                                                            borderRadius: '6px',
                                                            border: '1px solid #e5e7eb'
                                                        }}
                                                    >
                                                        <span style={{ fontSize: '14px', color: '#374151' }}>{ps}</span>
                                                        <button
                                                            onClick={() => handleRemoveProductString(sku.sku, ps)}
                                                            style={{
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                justifyContent: 'center',
                                                                width: '28px',
                                                                height: '28px',
                                                                borderRadius: '4px',
                                                                border: 'none',
                                                                backgroundColor: 'transparent',
                                                                color: '#ef4444',
                                                                cursor: 'pointer',
                                                                transition: 'background-color 0.2s'
                                                            }}
                                                            onMouseEnter={(e) => e.target.style.backgroundColor = '#fee2e2'}
                                                            onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
                                                        >
                                                            <X size={16} />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Add New ProductString */}
                                    <div>
                                        <h4 style={{ 
                                            fontSize: '14px', 
                                            fontWeight: 600, 
                                            color: '#374151',
                                            marginBottom: '12px'
                                        }}>
                                            Add ProductString:
                                        </h4>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <input
                                                type="text"
                                                placeholder="Enter ProductString to map to this SKU..."
                                                value={newProductString[sku.sku] || ''}
                                                onChange={(e) => setNewProductString({ 
                                                    ...newProductString, 
                                                    [sku.sku]: e.target.value 
                                                })}
                                                onKeyPress={(e) => {
                                                    if (e.key === 'Enter') {
                                                        handleAddProductString(sku.sku);
                                                    }
                                                }}
                                                style={{
                                                    flex: 1,
                                                    padding: '10px 12px',
                                                    borderRadius: '6px',
                                                    border: '1px solid #e5e7eb',
                                                    fontSize: '14px',
                                                    outline: 'none',
                                                    transition: 'border-color 0.2s'
                                                }}
                                                onFocus={(e) => e.target.style.borderColor = '#0f172a'}
                                                onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
                                            />
                                            <button
                                                onClick={() => handleAddProductString(sku.sku)}
                                                disabled={!newProductString[sku.sku]?.trim() || saving[sku.sku]}
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '6px',
                                                    padding: '10px 16px',
                                                    backgroundColor: '#0f172a',
                                                    color: '#fff',
                                                    border: 'none',
                                                    borderRadius: '6px',
                                                    fontSize: '14px',
                                                    fontWeight: 500,
                                                    cursor: (!newProductString[sku.sku]?.trim() || saving[sku.sku]) ? 'not-allowed' : 'pointer',
                                                    opacity: (!newProductString[sku.sku]?.trim() || saving[sku.sku]) ? 0.5 : 1,
                                                    transition: 'opacity 0.2s'
                                                }}
                                            >
                                                {saving[sku.sku] ? (
                                                    <>
                                                        <div style={{ 
                                                            width: '14px', 
                                                            height: '14px', 
                                                            border: '2px solid rgba(255,255,255,0.3)',
                                                            borderTop: '2px solid #fff',
                                                            borderRadius: '50%',
                                                            animation: 'spin 1s linear infinite'
                                                        }}></div>
                                                        Adding...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Plus size={16} />
                                                        Add
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

