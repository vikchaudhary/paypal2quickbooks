import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Save, Settings, CheckCircle, AlertCircle, X, ExternalLink, Tag } from 'lucide-react';
import { LineItemsTable } from './LineItemsTable';
import { getQBSettings } from '../services/settingsApi';
import { searchQBCustomers, getNextInvoiceNumber } from '../services/qbCustomerApi';
import { saveInvoiceToQB, getInvoiceRecord } from '../services/invoiceApi';
import { matchProducts, getProductMappings, setProductMappings } from '../services/productApi';

export function InvoiceForm({ po, poFilename, onInvoiceSaved }) {
    const poFilenameFromPO = po && po.filename ? po.filename : null;
    
    const [qbSettings, setQbSettings] = useState(null);
    const [qbConfigured, setQbConfigured] = useState(false);
    const [loadingSettings, setLoadingSettings] = useState(true);
    const [selectedCustomer, setSelectedCustomer] = useState(null);
    const [customerSearchTerm, setCustomerSearchTerm] = useState('');
    const [customerSearchResults, setCustomerSearchResults] = useState([]);
    const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
    const [searchingCustomers, setSearchingCustomers] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveSuccess, setSaveSuccess] = useState(false);
    const [saveError, setSaveError] = useState(null);
    const [savedInvoice, setSavedInvoice] = useState(null);
    const [isEditable, setIsEditable] = useState(true);
    const [invoiceNumber, setInvoiceNumber] = useState('');
    const [loadingInvoiceNumber, setLoadingInvoiceNumber] = useState(false);
    const [savedInvoiceRecord, setSavedInvoiceRecord] = useState(null);
    const [loadingInvoiceRecord, setLoadingInvoiceRecord] = useState(false);
    const [productMatches, setProductMatches] = useState({});
    const [matchingProducts, setMatchingProducts] = useState(false);
    const [skuData, setSkuData] = useState({}); // Store SKU name and description by SKU identifier
    const searchTimeoutRef = useRef(null);
    const dropdownRef = useRef(null);
    const loggedMatchesRef = useRef(new Set()); // Track which matches we've already logged

    // Load QuickBooks settings
    useEffect(() => {
        loadQBSettings();
    }, []);

    // Load saved invoice record when component mounts or poFilename changes
    useEffect(() => {
        // Reset saved invoice record when poFilename changes
        setSavedInvoiceRecord(null);
        
        if (poFilename) {
            loadInvoiceRecord(poFilename);
        }
    }, [poFilename]);

    // Auto-search for customer on load (only if no saved invoice exists)
    useEffect(() => {
        if (po && qbConfigured && po.vendor_name && !savedInvoiceRecord) {
            autoSearchCustomer(po.vendor_name);
        }
    }, [po, qbConfigured, savedInvoiceRecord]);

    // Match products when PO is loaded
    useEffect(() => {
        if (po && po.line_items && po.line_items.length > 0 && qbConfigured) {
            matchPOProducts();
        }
    }, [po, qbConfigured]);
    
    // Load SKU data when productMatches change (to ensure it's available for invoiceData)
    useEffect(() => {
        const loadSkuData = async () => {
            if (Object.keys(productMatches).length > 0) {
                try {
                    const mappingsData = await getProductMappings();
                    const skus = mappingsData.skus || {};
                    console.log('[SKU DEBUG] Loaded SKU data in useEffect:', { 
                        skuCount: Object.keys(skus).length, 
                        sampleSkus: Object.keys(skus).slice(0, 5)
                    });
                    setSkuData(skus);
                } catch (error) {
                    // Error loading SKU data
                }
            }
        };
        loadSkuData();
    }, [productMatches]);

    // Load next invoice number when customer is selected (only if no saved invoice exists)
    useEffect(() => {
        if (selectedCustomer && qbConfigured && isEditable && !savedInvoiceRecord) {
            loadNextInvoiceNumber(selectedCustomer.id);
        }
    }, [selectedCustomer, qbConfigured, isEditable, savedInvoiceRecord]);

    // Handle click outside dropdown
    useEffect(() => {
        function handleClickOutside(event) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowCustomerDropdown(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const loadQBSettings = async () => {
        try {
            setLoadingSettings(true);
            const settings = await getQBSettings();
            setQbSettings(settings);
            const configured = settings.configured || false;
            setQbConfigured(configured);
        } catch (error) {
            setQbConfigured(false);
        } finally {
            setLoadingSettings(false);
        }
    };

    const autoSearchCustomer = async (customerName) => {
        if (!customerName || !qbConfigured) return;
        
        // Don't auto-search if we already have a saved invoice
        if (savedInvoiceRecord) {
            return;
        }
        
        try {
            setSearchingCustomers(true);
            setSaveError(null);
            const customers = await searchQBCustomers(customerName);
            if (customers.length > 0) {
                // Try to find exact match first
                const exactMatch = customers.find(c => 
                    c.name.toLowerCase() === customerName.toLowerCase() ||
                    c.display_name.toLowerCase() === customerName.toLowerCase()
                );
                const selected = exactMatch || customers[0];
                setSelectedCustomer(selected);
                setCustomerSearchTerm(selected.display_name || selected.name);
                // Load invoice number immediately when customer is auto-selected (only if no saved invoice)
                if (selected.id && !savedInvoiceRecord) {
                    await loadNextInvoiceNumber(selected.id);
                }
            } else {
                // No results found, show the search term so user can search manually
                setCustomerSearchTerm(customerName);
            }
        } catch (error) {
            setSaveError(`Failed to search customers: ${error.message}`);
        } finally {
            setSearchingCustomers(false);
        }
    };

    const handleCustomerSearch = async (searchTerm) => {
        setCustomerSearchTerm(searchTerm);
        setSelectedCustomer(null);

        if (!searchTerm || !qbConfigured) {
            setCustomerSearchResults([]);
            setShowCustomerDropdown(false);
            return;
        }

        // Debounce search
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        searchTimeoutRef.current = setTimeout(async () => {
            try {
                setSearchingCustomers(true);
                setSaveError(null); // Clear previous errors
                const customers = await searchQBCustomers(searchTerm);
                setCustomerSearchResults(customers);
                // Show dropdown if we have results OR if search term is long enough (to show "no results")
                setShowCustomerDropdown(searchTerm.length >= 2);
            } catch (error) {
                setCustomerSearchResults([]);
                setShowCustomerDropdown(false);
                setSaveError(`Failed to search customers: ${error.message}`);
            } finally {
                setSearchingCustomers(false);
            }
        }, 300);
    };

    const handleSelectCustomer = async (customer) => {
        setSelectedCustomer(customer);
        setCustomerSearchTerm(customer.display_name || customer.name);
        setShowCustomerDropdown(false);
        // Load invoice number when customer is manually selected
        if (customer.id && qbConfigured && isEditable) {
            await loadNextInvoiceNumber(customer.id);
        }
    };

    const handleClearCustomer = () => {
        setSelectedCustomer(null);
        setCustomerSearchTerm('');
        setCustomerSearchResults([]);
        setShowCustomerDropdown(false);
        setInvoiceNumber(''); // Clear invoice number when customer is cleared
    };

    const loadNextInvoiceNumber = async (customerId) => {
        if (!customerId || !qbConfigured) return;
        
        // Don't load next invoice number if we already have a saved invoice
        if (savedInvoiceRecord) {
            return;
        }
        
        try {
            setLoadingInvoiceNumber(true);
            const result = await getNextInvoiceNumber(customerId);
            if (result.invoice_number) {
                setInvoiceNumber(result.invoice_number);
            }
        } catch (error) {
            // Fallback to default format if API fails
            setInvoiceNumber(`INV-${po?.po_number || '001'}`);
        } finally {
            setLoadingInvoiceNumber(false);
        }
    };

    const loadInvoiceRecord = async (filename) => {
        if (!filename) return;
        
        try {
            setLoadingInvoiceRecord(true);
            const result = await getInvoiceRecord(filename);
            if (result.invoice_record) {
                setSavedInvoiceRecord(result.invoice_record);
                setSavedInvoice({ 
                    Id: result.invoice_record.qb_invoice_id,
                    DocNumber: result.invoice_record.doc_number 
                });
                // ALWAYS set the invoice number from the saved record - this is the source of truth
                if (result.invoice_record.doc_number) {
                    setInvoiceNumber(result.invoice_record.doc_number);
                }
                setIsEditable(false); // Invoice already created, make form read-only
            }
        } catch (error) {
            // Error loading invoice record
        } finally {
            setLoadingInvoiceRecord(false);
        }
    };

    const matchPOProducts = async () => {
        if (!po || !po.line_items || po.line_items.length === 0 || !qbConfigured) {
            return;
        }

        try {
            setMatchingProducts(true);
            
            // Get existing mappings first
            const mappingsData = await getProductMappings();
            const existingMappings = mappingsData.mappings || {};
            
            // Extract product strings from PO line items
            const productStrings = po.line_items
                .map(item => item.product_name)
                .filter(name => name && name.trim());
            
            if (productStrings.length === 0) {
                return;
            }

            // Match ALL products using the matching service
            // The matching service will:
            // 1. First check Products database for existing mappings
            // 2. Verify the SKU exists in QuickBooks (by matching SKU's Name)
            // 3. Fall back to fuzzy matching if no database mapping exists
            const matchResult = await matchProducts(productStrings, 0.5);
            const matches = matchResult.matches || {};
            
            // Save new mappings (only for newly matched products, not database mappings)
            // But always update SKU metadata (including description) for all matched items
            const newMappings = {};
            const skuMetadata = {};
            for (const [productString, matchInfo] of Object.entries(matches)) {
                if (matchInfo.matched && matchInfo.sku) {
                    // Check if this was a database mapping (similarity = 1.0) or fuzzy match
                    const isDatabaseMapping = matchInfo.similarity === 1.0;
                    
                    // Only save mapping if it's a new fuzzy match (not from database)
                    if (!isDatabaseMapping) {
                        newMappings[productString] = matchInfo.sku;
                    }
                    
                    // Always update SKU metadata if we have item data (for both database and fuzzy matches)
                    // This ensures description is always up-to-date
                    if (matchInfo.item && matchInfo.item.Name && matchInfo.item.Id) {
                        skuMetadata[matchInfo.sku] = {
                            name: matchInfo.item.Name,
                            id: matchInfo.item.Id,
                            description: matchInfo.item.Description || null
                        };
                    }
                }
            }
            
            // Save new mappings and/or update SKU metadata
            if (Object.keys(newMappings).length > 0 || Object.keys(skuMetadata).length > 0) {
                await setProductMappings(newMappings, skuMetadata);
            }
            
            // Build complete match info for all products
            // Store both original and normalized keys to handle whitespace differences
            const allMatches = {};
            for (const productString of productStrings) {
                const normalizedPS = productString.trim();
                
                // Check match results (from matching service)
                const matchInfo = matches[productString] || matches[normalizedPS];
                
                if (matchInfo && matchInfo.matched) {
                    // Product was matched (either from database or fuzzy matching)
                    const isDatabaseMapping = matchInfo.similarity === 1.0;
                    allMatches[productString] = {
                        sku: matchInfo.sku,
                        matched: true,
                        similarity: matchInfo.similarity,
                        fromMapping: isDatabaseMapping
                    };
                    // Also store with normalized key for lookup
                    if (productString !== normalizedPS) {
                        allMatches[normalizedPS] = allMatches[productString];
                    }
                } else {
                    // No match found
                    allMatches[productString] = {
                        sku: null,
                        matched: false,
                        fromMapping: false
                    };
                }
            }
            
            setProductMatches(allMatches);
            
            // Fetch SKU data for matched items (reuse mappingsData from earlier)
            const skus = mappingsData.skus || {};
            console.log('[SKU DEBUG] Setting skuData:', { 
                skuCount: Object.keys(skus).length, 
                sampleSkus: Object.keys(skus).slice(0, 5),
                sampleSkuData: Object.keys(skus).length > 0 ? skus[Object.keys(skus)[0]] : null
            });
            setSkuData(skus);
        } catch (error) {
            // Set empty matches on error
            const emptyMatches = {};
            if (po && po.line_items) {
                po.line_items.forEach(item => {
                    if (item.product_name) {
                        emptyMatches[item.product_name] = {
                            sku: null,
                            matched: false,
                            fromMapping: false
                        };
                    }
                });
            }
            setProductMatches(emptyMatches);
        } finally {
            setMatchingProducts(false);
        }
    };
    
    // Get status from saved invoice record, then from PO
    // Don't use a default - only show status when we have actual data
    // The PO status comes from the backend which computes it using _determine_po_status()
    const invoiceStatus = savedInvoiceRecord?.status || po?.status || null;

    const getQuickBooksInvoiceUrl = (invoiceId) => {
        if (!invoiceId || !qbSettings) return null;
        const environment = qbSettings.environment || 'production';
        const baseUrl = environment === 'sandbox' 
            ? 'https://sandbox.qbo.intuit.com'
            : 'https://app.qbo.intuit.com';
        return `${baseUrl}/app/invoice?txnId=${invoiceId}`;
    };

    const handleSaveToQuickBooks = async () => {
        if (!selectedCustomer) {
            setSaveError('Please select a customer');
            return;
        }

        if (!po) {
            setSaveError('No PO data available');
            return;
        }

        try {
            setSaving(true);
            setSaveError(null);

            // Convert PO data to backend format
            // Use invoiceData.lineItems which has the matched SKU information
            const items = (invoiceData?.lineItems || po.line_items || []).map((item, index) => {
                // Use the matched SKU if available from invoiceData, otherwise use original product_name
                const poItem = po.line_items?.[index];
                const productName = item.product || item.product_name || poItem?.product_name || '';
                const sku = item.sku || null; // Include matched SKU if available
                
                return {
                    product_name: productName,
                    sku: sku, // Send SKU to backend for direct lookup
                    quantity: parseFloat(item.qty || item.quantity || poItem?.quantity || 0),
                    rate: parseFloat(
                        (item.rate && typeof item.rate === 'number' ? item.rate : 
                         item.rate && typeof item.rate === 'string' ? item.rate.replace(/[^0-9.-]+/g, '') :
                         item.unit_price?.replace(/[^0-9.-]+/g, '') || 
                         poItem?.unit_price?.replace(/[^0-9.-]+/g, '') || 0)
                    ),
                    price: parseFloat(
                        (item.amount && typeof item.amount === 'number' ? item.amount :
                         item.amount && typeof item.amount === 'string' ? item.amount.replace(/[^0-9.-]+/g, '') :
                         poItem?.amount?.replace(/[^0-9.-]+/g, '') || 0)
                    )
                };
            });
            
            const invoiceDataToSend = {
                customer: po.vendor_name || 'Unknown',
                po_number: po.po_number || 'Unknown',
                invoice_number: invoiceNumber || `INV-${po.po_number || '001'}`,
                order_date: po.date || new Date().toISOString().split('T')[0],
                delivery_date: po.delivery_date || null,
                invoice_amount: parseFloat(po.total_amount?.replace(/[^0-9.-]+/g, '') || 0),
                items: items
            };

            const result = await saveInvoiceToQB(selectedCustomer.id, invoiceDataToSend, poFilename);
            
            if (result.status === 'created' || result.status === 'exists') {
                setSaveSuccess(true);
                setSavedInvoice(result.invoice);
                setIsEditable(false);
                // Reload invoice record to get the saved data - this will set the invoice number from the saved record
                if (poFilename) {
                    await loadInvoiceRecord(poFilename);
                } else if (result.invoice && result.invoice.DocNumber) {
                    // Fallback: if no filename, use the invoice number from the response
                    setInvoiceNumber(result.invoice.DocNumber);
                    }
                // Refresh PO list to update status
                if (onInvoiceSaved) {
                    onInvoiceSaved();
                }
            } else {
                setSaveError(result.error || 'Failed to save invoice');
            }
        } catch (error) {
            setSaveError(error.message || 'Failed to save invoice to QuickBooks');
        } finally {
            setSaving(false);
        }
    };

    const goToSettings = () => {
        // Navigate to settings - for now just alert, will be implemented with routing
        alert('Please configure QuickBooks settings first. Settings page coming soon.');
    };

    // Helper function to convert date to YYYY-MM-DD format
    const convertDateToISO = (dateStr) => {
        if (!dateStr || dateStr === 'Unknown') return null;
        
        // Remove any extra whitespace
        dateStr = dateStr.trim();
        
        // Try to parse various date formats
        // Handle MM/DD/YYYY or DD/MM/YYYY (ambiguous format)
        const slashMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
        if (slashMatch) {
            const first = parseInt(slashMatch[1]);
            const second = parseInt(slashMatch[2]);
            const year = parseInt(slashMatch[3]);
            
            // Heuristic: if first number > 12, it's likely DD/MM/YYYY
            // If first <= 12 and second > 12, it's MM/DD/YYYY
            // If both <= 12, try MM/DD/YYYY first (US format is more common)
            let month, day;
            if (first > 12) {
                // DD/MM/YYYY format (day > 12, so first must be day)
                day = first;
                month = second;
            } else if (second > 12) {
                // MM/DD/YYYY format (second > 12, so second must be day)
                month = first;
                day = second;
            } else {
                // Both <= 12, ambiguous - try MM/DD/YYYY first (US format)
                // But also check if second could be a valid month
                if (second <= 12 && first <= 31) {
                    // Try DD/MM/YYYY
                    day = first;
                    month = second;
                } else {
                    // Try MM/DD/YYYY
                    month = first;
                    day = second;
                }
            }
            
            // Validate month and day
            if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            }
        }
        
        // Handle YYYY-MM-DD format (already correct)
        const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (isoMatch) {
            return dateStr;
        }
        
        // Handle DD-MM-YYYY format
        const dashMatch = dateStr.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
        if (dashMatch) {
            const first = parseInt(dashMatch[1]);
            const second = parseInt(dashMatch[2]);
            const year = parseInt(dashMatch[3]);
            
            // Assume DD-MM-YYYY format
            const day = first;
            const month = second;
            
            if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            }
        }
        
        // Try JavaScript Date parsing as fallback
        try {
            // Try parsing as MM/DD/YYYY first (US format)
            const usDate = new Date(dateStr);
            if (!isNaN(usDate.getTime())) {
                const year = usDate.getFullYear();
                const month = String(usDate.getMonth() + 1).padStart(2, '0');
                const day = String(usDate.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            }
        } catch (e) {
            // Ignore
        }
        
        return null;
    };

    // Convert PO data to invoice format for display
    // Use useMemo to recompute when po, productMatches, or skuData changes
    const invoiceData = useMemo(() => {
        if (!po) return null;
        
        // Reset logged matches when PO changes (using poFilename as key)
        const currentPOKey = poFilename || (po && po.po_number) || 'unknown';
        if (!loggedMatchesRef.current.poKey || loggedMatchesRef.current.poKey !== currentPOKey) {
            loggedMatchesRef.current = new Set();
            loggedMatchesRef.current.poKey = currentPOKey;
        }
        
        return {
            invoiceNumber: invoiceNumber || `INV-${po.po_number || '001'}`,
            referencePO: po.po_number || '',
            invoiceDate: convertDateToISO(po.date) || new Date().toISOString().split('T')[0],
            dueDate: convertDateToISO(po.delivery_date) || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            lineItems: (po.line_items || []).map((item, index) => {
                const productName = item.product_name || '';
                // Try exact match first, then normalized match
                let matchInfo = productMatches[productName];
                if (!matchInfo) {
                    // Try with trimmed version
                    const trimmedName = productName.trim();
                    matchInfo = productMatches[trimmedName];
                }
                // Fallback to empty match info
                if (!matchInfo) {
                    matchInfo = { matched: false, sku: null };
                }
                
                // If matched, get SKU name and description from Products database
                let displayProduct = productName;
                let displayDescription = item.description;
                
                if (matchInfo.matched && matchInfo.sku) {
                    // Create a unique key for this match to avoid duplicate logs
                    const matchKey = `${productName}::${matchInfo.sku}`;
                    const shouldLog = Object.keys(skuData).length > 0 && !loggedMatchesRef.current.has(matchKey);
                    
                    // Try to find SKU in skuData with multiple lookup strategies
                    let skuInfo = null;
                    let lookupMethod = null;
                    
                    // Strategy 1: Direct lookup
                    if (skuData[matchInfo.sku]) {
                        skuInfo = skuData[matchInfo.sku];
                        lookupMethod = 'direct';
                    } else {
                        // Strategy 2: Case-insensitive lookup
                        const skuLower = matchInfo.sku.toLowerCase();
                        const foundKey = Object.keys(skuData).find(key => key.toLowerCase() === skuLower);
                        if (foundKey) {
                            skuInfo = skuData[foundKey];
                            lookupMethod = 'case-insensitive';
                        } else {
                            // Strategy 3: Match by SKU name
                            const foundByName = Object.values(skuData).find(sku => 
                                sku.name && sku.name.toLowerCase() === skuLower
                            );
                            if (foundByName) {
                                skuInfo = foundByName;
                                lookupMethod = 'by-name';
                            }
                        }
                    }
                    
                    if (skuInfo) {
                        // Use SKU's name and description from Products database
                        displayProduct = skuInfo.name || productName;
                        // Description should always be available if SKU is in database
                        // If description is null/undefined, it means it wasn't saved properly
                        displayDescription = skuInfo.description || skuInfo.name || productName;
                        
                        // Log match information (only once per match)
                        if (shouldLog) {
                            loggedMatchesRef.current.add(matchKey);
                            
                            // Debug: Log the full skuInfo to see what's actually there
                            console.log('[SKU DEBUG] Match found:', {
                                productName: productName,
                                matchedSKU: skuInfo.name || matchInfo.sku,
                                skuDescription: skuInfo.description || '(no description)',
                                lookupMethod: lookupMethod,
                                skuInfoKeys: Object.keys(skuInfo),
                                fullSkuInfo: skuInfo
                            });
                        }
                    } else {
                        if (shouldLog) {
                            loggedMatchesRef.current.add(matchKey);
                            console.log(`[SKU DEBUG] No match found for SKU "${matchInfo.sku}" in skuData`, {
                                availableSkuKeys: Object.keys(skuData).slice(0, 10),
                                matchInfoSku: matchInfo.sku
                            });
                        }
                    }
                }
                
                return {
                    id: index + 1,
                    product: displayProduct,
                    description: displayDescription,
                    qty: parseFloat(item.quantity || 0),
                    rate: parseFloat((item.unit_price && item.unit_price.replace(/[^0-9.-]+/g, '')) || 0),
                    amount: parseFloat((item.amount && item.amount.replace(/[^0-9.-]+/g, '')) || 0),
                    // Add match information
                    matched: matchInfo.matched,
                    sku: matchInfo.sku,
                    matchSimilarity: matchInfo.similarity,
                    fromMapping: matchInfo.fromMapping
                };
            })
        };
    }, [po, productMatches, skuData, invoiceNumber, poFilename]);

    if (!po || !po.vendor_name) {
        return (
            <div style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>
                <p>No PO data available. Please extract PO details first.</p>
            </div>
        );
    }

    // Show saved invoice info if it exists
    const showSavedInvoiceInfo = savedInvoiceRecord && !isEditable;

    return (
        <div style={{ 
            padding: '20px', 
            paddingBottom: '100px', 
            height: '100%', 
            overflowY: 'auto', 
            backgroundColor: '#f9fafb',
            boxSizing: 'border-box'
        }}>
            {/* Status Badge - Only show when status is available */}
            {invoiceStatus && (
                <div style={{ 
                    backgroundColor: '#fff', 
                    borderRadius: '12px', 
                    padding: '16px 20px', 
                    marginBottom: '20px',
                    border: '1px solid #e5e7eb',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Tag size={18} color="#6b7280" />
                        <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>Status:</span>
                        <StatusBadge status={invoiceStatus} />
                    </div>
                </div>
            )}
            {!invoiceStatus && loadingInvoiceRecord && (
                <div style={{ 
                    backgroundColor: '#fff', 
                    borderRadius: '12px', 
                    padding: '16px 20px', 
                    marginBottom: '20px',
                    border: '1px solid #e5e7eb',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                }}>
                    <Tag size={18} color="#6b7280" />
                    <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>Status:</span>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>Loading...</span>
                </div>
            )}
            
            {/* Saved Invoice Info */}
            {showSavedInvoiceInfo && (
                <div style={{ 
                    backgroundColor: '#f0fdf4', 
                    borderRadius: '12px', 
                    padding: '20px', 
                    marginBottom: '20px',
                    border: '1px solid #bbf7d0'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: '#166534', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <CheckCircle size={18} />
                                Invoice Created Successfully
                            </div>
                            <div style={{ fontSize: '13px', color: '#15803d', marginBottom: '4px' }}>
                                Invoice #{savedInvoiceRecord.doc_number} was created on {new Date(savedInvoiceRecord.created_at).toLocaleDateString()}
                            </div>
                            {savedInvoiceRecord.qb_invoice_id && (
                                <a
                                    href={getQuickBooksInvoiceUrl(savedInvoiceRecord.qb_invoice_id)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        fontSize: '13px',
                                        color: '#0f172a',
                                        textDecoration: 'none',
                                        marginTop: '8px',
                                        padding: '6px 12px',
                                        backgroundColor: '#fff',
                                        borderRadius: '6px',
                                        border: '1px solid #bbf7d0',
                                        fontWeight: 500,
                                        transition: 'background-color 0.2s'
                                    }}
                                    onMouseEnter={(e) => e.target.style.backgroundColor = '#f9fafb'}
                                    onMouseLeave={(e) => e.target.style.backgroundColor = '#fff'}
                                >
                                    <ExternalLink size={14} />
                                    Open in QuickBooks
                                </a>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* QuickBooks Account Status */}
            <div style={{ 
                backgroundColor: '#fff', 
                borderRadius: '12px', 
                padding: '20px', 
                marginBottom: '20px',
                border: '1px solid #e5e7eb'
            }}>
                {loadingSettings ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280' }}>
                        <div style={{ 
                            width: '16px', 
                            height: '16px', 
                            border: '2px solid #e5e7eb',
                            borderTop: '2px solid #6b7280',
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite'
                        }}></div>
                        <span>Loading QuickBooks settings...</span>
                    </div>
                ) : qbConfigured ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827', marginBottom: '4px' }}>
                                QuickBooks Connected
                            </div>
                            <div style={{ fontSize: '13px', color: '#6b7280' }}>
                                Environment: {qbSettings?.environment || 'production'}
                                {qbSettings?.realm_id && ` • Realm: ${qbSettings.realm_id}`}
                            </div>
                        </div>
                        <CheckCircle size={20} color="#10b981" />
                    </div>
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: '#ef4444', marginBottom: '4px' }}>
                                QuickBooks Not Configured
                            </div>
                            <div style={{ fontSize: '13px', color: '#6b7280' }}>
                                Please configure QuickBooks settings to save invoices
                            </div>
                        </div>
                        <button
                            onClick={goToSettings}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                backgroundColor: '#0f172a',
                                color: '#fff',
                                border: 'none',
                                padding: '8px 16px',
                                borderRadius: '6px',
                                fontSize: '13px',
                                fontWeight: 500,
                                cursor: 'pointer'
                            }}
                        >
                            <Settings size={14} />
                            Go to Settings
                        </button>
                    </div>
                )}
            </div>

            {/* Customer Selection */}
            {qbConfigured && (
                <div style={{ 
                    backgroundColor: '#fff', 
                    borderRadius: '12px', 
                    padding: '24px', 
                    marginBottom: '20px',
                    border: '1px solid #e5e7eb'
                }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>
                        Customer Name
                    </h3>
                    <div style={{ position: 'relative' }} ref={dropdownRef}>
                        {selectedCustomer ? (
                            // Display selected customer as a label with clear button
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '10px 12px',
                                borderRadius: '6px',
                                border: '1px solid #d1d5db',
                                backgroundColor: '#f9fafb',
                                minHeight: '40px'
                            }}>
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    flex: 1,
                                    minWidth: 0
                                }}>
                                    <CheckCircle size={16} color="#10b981" />
                                    <span style={{
                                        fontSize: '14px',
                                        color: '#111827',
                                        fontWeight: 500,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                    }}>
                                        {selectedCustomer.display_name || selectedCustomer.name}
                                    </span>
                                    {selectedCustomer.company_name && (
                                        <span style={{
                                            fontSize: '12px',
                                            color: '#6b7280',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap'
                                        }}>
                                            ({selectedCustomer.company_name})
                                        </span>
                                    )}
                                </div>
                                <button
                                    onClick={handleClearCustomer}
                                    disabled={!isEditable || saving}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        width: '24px',
                                        height: '24px',
                                        borderRadius: '4px',
                                        border: 'none',
                                        backgroundColor: 'transparent',
                                        color: '#6b7280',
                                        cursor: (!isEditable || saving) ? 'not-allowed' : 'pointer',
                                        opacity: (!isEditable || saving) ? 0.5 : 1,
                                        transition: 'background-color 0.2s, color 0.2s',
                                        flexShrink: 0,
                                        marginLeft: '8px'
                                    }}
                                    onMouseEnter={(e) => {
                                        if (isEditable && !saving) {
                                            e.target.style.backgroundColor = '#e5e7eb';
                                            e.target.style.color = '#ef4444';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (isEditable && !saving) {
                                            e.target.style.backgroundColor = 'transparent';
                                            e.target.style.color = '#6b7280';
                                        }
                                    }}
                                    title="Clear customer selection"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        ) : (
                            // Search input when no customer selected
                            <>
                                <input
                                    type="text"
                                    value={customerSearchTerm}
                                    onChange={(e) => handleCustomerSearch(e.target.value)}
                                    onFocus={() => {
                                        // Show dropdown if we have a search term and results
                                        if (customerSearchTerm.length >= 2) {
                                            setShowCustomerDropdown(true);
                                        }
                                    }}
                                    placeholder="Search for customer in QuickBooks..."
                                    disabled={!isEditable || saving}
                                    style={{
                                        ...inputStyle,
                                        paddingRight: searchingCustomers ? '40px' : '12px',
                                        backgroundColor: '#fff'
                                    }}
                                />
                                {searchingCustomers && (
                                    <div style={{
                                        position: 'absolute',
                                        right: '12px',
                                        top: '50%',
                                        transform: 'translateY(-50%)'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            border: '2px solid #e5e7eb',
                                            borderTop: '2px solid #6b7280',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }}></div>
                                    </div>
                                )}
                            </>
                        )}
                        {!selectedCustomer && showCustomerDropdown && customerSearchTerm.length >= 2 && (
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                left: 0,
                                right: 0,
                                marginTop: '4px',
                                backgroundColor: '#fff',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                                maxHeight: '300px',
                                overflowY: 'auto',
                                zIndex: 1000,
                                minHeight: '40px'
                            }}>
                                {searchingCustomers ? (
                                    <div style={{
                                        padding: '16px',
                                        textAlign: 'center',
                                        color: '#6b7280',
                                        fontSize: '14px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '8px'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            border: '2px solid #e5e7eb',
                                            borderTop: '2px solid #6b7280',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }}></div>
                                        Searching...
                                    </div>
                                ) : customerSearchResults.length > 0 ? (
                                    customerSearchResults.map((customer) => (
                                        <div
                                            key={customer.id}
                                            onClick={() => handleSelectCustomer(customer)}
                                            style={{
                                                padding: '12px',
                                                cursor: 'pointer',
                                                borderBottom: '1px solid #f3f4f6',
                                                backgroundColor: selectedCustomer?.id === customer.id ? '#f3f4f6' : '#fff'
                                            }}
                                            onMouseEnter={(e) => e.target.style.backgroundColor = '#f9fafb'}
                                            onMouseLeave={(e) => e.target.style.backgroundColor = selectedCustomer?.id === customer.id ? '#f3f4f6' : '#fff'}
                                        >
                                            <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>
                                                {customer.display_name || customer.name}
                                            </div>
                                            {customer.company_name && (
                                                <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                                                    {customer.company_name}
                                                </div>
                                            )}
                                        </div>
                                    ))
                                ) : (
                                    <div style={{
                                        padding: '16px',
                                        textAlign: 'center',
                                        color: '#6b7280',
                                        fontSize: '14px'
                                    }}>
                                        No customers found matching "{customerSearchTerm}"
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                    {!selectedCustomer && customerSearchTerm && customerSearchTerm.length >= 2 && !searchingCustomers && customerSearchResults.length === 0 && showCustomerDropdown && (
                        <div style={{ 
                            marginTop: '8px', 
                            padding: '8px 12px', 
                            backgroundColor: '#fef3c7', 
                            borderRadius: '6px',
                            border: '1px solid #fde68a'
                        }}>
                            <div style={{ fontSize: '12px', color: '#92400e' }}>
                                No customers found. Try a different search term or check your QuickBooks connection.
                            </div>
                        </div>
                    )}
                    {!selectedCustomer && !customerSearchTerm && (
                        <div style={{ 
                            marginTop: '8px', 
                            fontSize: '12px', 
                            color: '#6b7280' 
                        }}>
                            Start typing to search for a customer in QuickBooks
                        </div>
                    )}
                </div>
            )}

            {/* Invoice Details (Read-only after save) */}
            <div style={{ 
                backgroundColor: '#fff', 
                borderRadius: '12px', 
                padding: '24px', 
                marginBottom: '20px',
                border: '1px solid #e5e7eb',
                opacity: isEditable ? 1 : 0.6
            }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '20px' }}>
                    Invoice Details {!isEditable && '(Saved)'}
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                    <FormGroup label="Invoice Number">
                        <div style={{ position: 'relative' }}>
                        <input
                            type="text"
                                value={savedInvoiceRecord?.doc_number || invoiceNumber || invoiceData?.invoiceNumber || ''}
                                onChange={(e) => {
                                    // Only allow editing if no saved invoice exists
                                    if (!savedInvoiceRecord && isEditable) {
                                        setInvoiceNumber(e.target.value);
                                    }
                                }}
                                disabled={!isEditable || loadingInvoiceNumber || !!savedInvoiceRecord}
                                placeholder={loadingInvoiceNumber ? "Loading..." : savedInvoiceRecord ? "From saved invoice" : "Invoice number"}
                                readOnly={!!savedInvoiceRecord}
                                style={{
                                    ...inputStyle,
                                    paddingRight: loadingInvoiceNumber ? '40px' : '12px',
                                    backgroundColor: savedInvoiceRecord ? '#f3f4f6' : '#fff',
                                    cursor: savedInvoiceRecord ? 'not-allowed' : 'text'
                                }}
                            />
                            {loadingInvoiceNumber && (
                                <div style={{
                                    position: 'absolute',
                                    right: '12px',
                                    top: '50%',
                                    transform: 'translateY(-50%)'
                                }}>
                                    <div style={{ 
                                        width: '16px', 
                                        height: '16px', 
                                        border: '2px solid #e5e7eb',
                                        borderTop: '2px solid #6b7280',
                                        borderRadius: '50%',
                                        animation: 'spin 1s linear infinite'
                                    }}></div>
                                </div>
                            )}
                        </div>
                        {savedInvoiceRecord && (
                            <div style={{ 
                                marginTop: '4px', 
                                fontSize: '12px', 
                                color: '#6b7280' 
                            }}>
                                Invoice number is locked from saved invoice record
                            </div>
                        )}
                    </FormGroup>
                    <FormGroup label="Reference PO">
                        <input
                            type="text"
                            value={invoiceData?.referencePO || ''}
                            disabled={!isEditable}
                            style={inputStyle}
                        />
                    </FormGroup>
                    <FormGroup label="Invoice Date">
                        <input
                            type="date"
                            value={invoiceData?.invoiceDate || ''}
                            disabled={!isEditable}
                            style={inputStyle}
                        />
                    </FormGroup>
                    <FormGroup label="Due Date">
                        <input
                            type="date"
                            value={invoiceData?.dueDate || ''}
                            disabled={!isEditable}
                            style={inputStyle}
                        />
                    </FormGroup>
                    {/* Show Total Amount for saved invoices */}
                    {savedInvoiceRecord && (
                        <FormGroup label="Total Amount">
                            <input
                                type="text"
                                value={po?.total_amount || '$0.00'}
                                disabled={true}
                                readOnly={true}
                                style={{
                                    ...inputStyle,
                                    backgroundColor: '#f3f4f6',
                                    cursor: 'not-allowed',
                                    fontWeight: 600
                                }}
                            />
                        </FormGroup>
                    )}
                </div>
            </div>

            {/* Line Items */}
            <div style={{ 
                backgroundColor: '#fff', 
                borderRadius: '12px', 
                padding: '24px', 
                marginBottom: '20px',
                border: '1px solid #e5e7eb',
                opacity: isEditable ? 1 : 0.6
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: 0 }}>
                        Products
                    </h3>
                    <div style={{ 
                        fontSize: '12px', 
                        color: '#6b7280',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                    }}>
                        <span>QuickBooks products are read-only</span>
                    </div>
                </div>
                {matchingProducts && (
                    <div style={{ 
                        marginBottom: '16px', 
                        padding: '12px', 
                        backgroundColor: '#fef3c7', 
                        borderRadius: '6px',
                        border: '1px solid #fde68a',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}>
                        <div style={{ 
                            width: '16px', 
                            height: '16px', 
                            border: '2px solid #fde68a',
                            borderTop: '2px solid #92400e',
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite'
                        }}></div>
                        <span style={{ fontSize: '13px', color: '#92400e' }}>
                            Matching products to QuickBooks SKUs...
                        </span>
                    </div>
                )}
                <LineItemsTable
                    lineItems={invoiceData?.lineItems || []}
                    editable={isEditable}
                />
                </div>

            {/* Success/Error Messages */}
            {saveSuccess && (
                <div style={{
                    padding: '16px',
                    backgroundColor: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    borderRadius: '8px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px'
                }}>
                    <CheckCircle size={20} color="#10b981" />
                    <div>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: '#166534' }}>
                            Invoice saved successfully to QuickBooks!
                        </div>
                        {savedInvoice && (
                            <div style={{ fontSize: '13px', color: '#15803d', marginTop: '4px' }}>
                                Invoice #{savedInvoice.DocNumber || savedInvoice.Id} created
                        </div>
                        )}
                    </div>
                </div>
            )}

            {saveError && (
                <div style={{
                    padding: '16px',
                    backgroundColor: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderRadius: '8px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px'
                }}>
                    <AlertCircle size={20} color="#ef4444" />
                    <div>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: '#991b1b' }}>
                            Error saving invoice
                        </div>
                        <div style={{ fontSize: '13px', color: '#dc2626', marginTop: '4px' }}>
                            {saveError}
                        </div>
                    </div>
                </div>
            )}

            {/* Save Button */}
            {qbConfigured && isEditable && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <button
                        onClick={handleSaveToQuickBooks}
                        disabled={!selectedCustomer || saving}
                        style={{
                            ...primaryButtonStyle,
                            opacity: (!selectedCustomer || saving) ? 0.5 : 1,
                            cursor: (!selectedCustomer || saving) ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}
                    >
                        {saving ? (
                            <>
                                <div style={{ 
                                    width: '16px', 
                                    height: '16px', 
                                    border: '2px solid rgba(255,255,255,0.3)',
                                    borderTop: '2px solid #fff',
                                    borderRadius: '50%',
                                    animation: 'spin 1s linear infinite'
                                }}></div>
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save size={16} />
                                Save to QuickBooks
                            </>
                        )}
                    </button>
                </div>
            )}
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
    backgroundColor: '#0f172a',
    color: '#fff',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: 500,
    transition: 'background-color 0.2s'
};

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
            fontSize: '12px',
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
