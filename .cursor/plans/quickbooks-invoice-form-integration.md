# QuickBooks Invoice Form Integration Plan

## Overview
Extend the application to convert extracted PO details into QuickBooks invoices via the QuickBooks API. When "Convert to Invoice" is clicked, display an Invoice form tab/page (InvoiceForm.jsx) where users can select a QuickBooks customer and save the invoice.

## Data Flow
1. User clicks "Convert to Invoice" button in PODetails component
2. Navigate to Invoice tab/page (InvoiceForm component)
3. InvoiceForm displays connected QuickBooks account (or link to settings if not configured)
4. Auto-search for customer matching PO customer name
5. User selects/confirms customer from QuickBooks
6. User clicks "Save to QuickBooks" button
7. Backend creates invoice via QuickBooks API
8. Invoice form becomes non-editable on success, or displays error message

## Backend Components

### 1. Settings Service
**File**: `backend/src/beanscounter/services/settings_service.py`
- `save_qb_credentials(client_id, client_secret, refresh_token, realm_id, environment)` - Save encrypted credentials (single account)
- `get_qb_credentials()` - Retrieve and decrypt credentials (single account)
- `has_qb_credentials()` - Check if credentials are configured
- `delete_qb_credentials()` - Remove QuickBooks configuration
- `test_qb_connection()` - Test API connection with stored credentials
- **Storage**: JSON file at `backend/data/settings.json` (encrypted)

### 2. Encryption Utility
**File**: `backend/src/beanscounter/core/encryption.py`
- `encrypt_value(value: str, key: str)` - Encrypt a string
- `decrypt_value(encrypted_value: str, key: str)` - Decrypt a string
- Uses `cryptography` library (Fernet symmetric encryption)
- Key from environment variable `ENCRYPTION_KEY`

### 3. PO to Invoice Converter Service
**File**: `backend/src/beanscounter/services/po_to_invoice_service.py`
- `convert_po_to_qb_invoice(po_details: Dict, customer_id: str)` - Main conversion function
  - Retrieves QB credentials (single account)
  - Initializes QuickBooksClient
  - Uses provided customer_id (must be valid QuickBooks customer ID)
  - Maps PO data to QB invoice format
  - Creates invoice via QuickBooks API
  - Returns invoice creation result
- `_map_po_items_to_qb_lines(po_items: List)` - Convert PO line items to QuickBooks line items
- `_format_date_for_qb(date_str: str)` - Convert date to YYYY-MM-DD format
- Uses existing `QuickBooksClient` from `beanscounter.integrations.quickbooks_client`

### 4. QuickBooks Customer Service
**File**: `backend/src/beanscounter/services/qb_customer_service.py` (new)
- `search_customers(search_term: str)` - Search QuickBooks customers by name
  - Uses QuickBooksClient.query() to search customers
  - Returns list of matching customers: `[{id, name, display_name, ...}, ...]`
- `get_customer(customer_id: str)` - Get specific customer by ID
- Uses existing `QuickBooksClient` from `beanscounter.integrations.quickbooks_client`

### 5. Settings API Router
**File**: `backend/src/api/routers/settings.py`
- `GET /settings/quickbooks` - Get QuickBooks settings (masked secrets)
- `POST /settings/quickbooks` - Create/update QuickBooks settings
  - Request body: `{client_id, client_secret, refresh_token, realm_id, environment}`
- `DELETE /settings/quickbooks` - Delete QuickBooks settings
- `POST /settings/quickbooks/test` - Test connection with stored credentials

### 6. QuickBooks Customer Search API
**File**: `backend/src/api/routers/quickbooks.py` (new)
- `GET /quickbooks/customers/search?q={search_term}` - Search QuickBooks customers
  - Returns list of customers matching search term
  - Response: `[{id, name, display_name, ...}, ...]`
- `GET /quickbooks/customers/{customer_id}` - Get specific customer details

### 7. Invoice Save API Endpoint
**File**: `backend/src/api/routers/invoices.py` (extend existing)
- `POST /invoices/save-to-quickbooks` - Save invoice to QuickBooks
  - Request body: `{customer_id: str, invoice_data: PODetails}`
  - Response: `{status: "created"|"exists"|"error", invoice: {...}, error?: string}`
  - Uses `po_to_invoice_service.convert_po_to_qb_invoice()` with specified customer_id
  - Returns error if QuickBooks credentials not configured

### 8. Update FastAPI App
**File**: `backend/src/api/app.py` (update existing)
- Include settings router: `app.include_router(settings_router)`
- Include quickbooks router: `app.include_router(quickbooks_router)`

## Frontend Components

### 1. Settings Page (Main)
**File**: `frontend/src/pages/SettingsPage.tsx`
- Main settings page with navigation to different settings sections
- Layout with sidebar or tabs for different settings categories
- Sections: QuickBooks Settings, etc. (extensible for future settings)

### 2. QuickBooks Settings Page
**File**: `frontend/src/pages/QuickBooksSettingsPage.tsx`
- Dedicated page for QuickBooks configuration
- Shows current settings status (configured/not configured)
- Form fields:
  - Client ID (text input, password-masked)
  - Client Secret (text input, password-masked)
  - Refresh Token (text input, password-masked)
  - Realm ID (text input)
  - Environment (select: Production/Sandbox)
- Save button to store credentials
- Test Connection button
- Delete button to remove configuration
- Form validation
- Displays connection status

### 3. Enhanced PODetails Component
**File**: `frontend/src/components/PODetails.tsx` (update existing)
- Add "Convert to Invoice" button
- When clicked, navigate to Invoice tab/page (InvoiceForm component)
- Pass PO details data to Invoice form via route params or state

### 4. Invoice Form Component
**File**: `frontend/src/components/InvoiceForm.tsx` (new)
- Display connected QuickBooks account information
- Show button/link to Settings > QuickBooks if credentials not configured
- Customer Name field with QuickBooks customer search/selection:
  - Auto-search for customer matching PO customer name on component load
  - Auto-select customer if exact match found
  - Manual search/select dropdown if no match or user wants to change
  - Search as user types (debounced)
  - Display customer list in dropdown
- "Save to QuickBooks" button
- Show loading state during save
- Display success message after successful save
- Display error message on failure (keep form editable)
- Make form non-editable after successful save
- Display invoice details after successful creation

### 5. Settings API Service
**File**: `frontend/src/services/settingsApi.ts`
- `getQBSettings()` - Fetch QuickBooks settings (masked)
- `saveQBSettings(settingsData)` - Create/update QuickBooks settings
- `deleteQBSettings()` - Delete QuickBooks settings
- `testQBConnection()` - Test connection with stored credentials

### 6. QuickBooks Customer Search API Service
**File**: `frontend/src/services/qbCustomerApi.ts` (new)
- `searchQBCustomers(searchTerm)` - Search QuickBooks customers by name
- `getQBCustomer(customerId)` - Get specific customer details
- Error handling

### 7. Invoice Save API Service
**File**: `frontend/src/services/invoiceApi.ts` (new)
- `saveInvoiceToQB(customerId, invoiceData)` - Save invoice to QuickBooks
  - Request body: `{customer_id, invoice_data: PODetails}`
- Error handling and response parsing

### 8. Updated Sidebar
**File**: `frontend/src/components/Sidebar.tsx` (update existing)
- Add "Settings" navigation item linking to SettingsPage
- Settings page will have sub-navigation for QuickBooks Settings

### 9. Updated App Routing
**File**: `frontend/src/App.tsx` (update existing)
- Add route for Invoice tab/page: `/invoice/:poId` or `/po/:poId/invoice`
- Pass PO data to InvoiceForm component via route params or context

### 10. Type Definitions
**File**: `frontend/src/types/index.ts` (extend existing)
- `QuickBooksSettings` interface: `{client_id, client_secret, refresh_token, realm_id, environment}`
- `QBSettingsFormData` interface
- `QBCustomer` interface: `{id, name, display_name, ...}`
- `InvoiceSaveRequest` interface: `{customer_id, invoice_data: PODetails}`
- `InvoiceSaveResponse` interface: `{status, invoice, error?}`

## Data Transformation Mapping

PO Data → QuickBooks Invoice:
- `customer` → `CustomerRef` (uses provided customer_id from InvoiceForm)
- `po_number` → `DocNumber`
- `order_date` → `TxnDate` (format: YYYY-MM-DD)
- `delivery_date` → `DueDate` (format: YYYY-MM-DD, optional)
- `items[]` → `Line[]` (each item becomes `SalesItemLineDetail`)
  - `product_name` → Item name (via `QuickBooksClient.ensure_item()`)
  - `quantity` → `Qty`
  - `rate` → `UnitPrice`
  - `price` → `Amount` (qty * rate)
  - Taxable status → `TaxCodeRef` ("TAX" or "NON")

## File Structure

### Backend New Files
```
backend/src/
├── api/routers/
│   ├── settings.py (new)
│   └── quickbooks.py (new - customer search endpoints)
├── beanscounter/
│   ├── core/
│   │   └── encryption.py (new)
│   └── services/
│       ├── settings_service.py (new)
│       ├── po_to_invoice_service.py (new)
│       └── qb_customer_service.py (new)
└── data/
    └── settings.json (new - encrypted credentials)
```

### Frontend New Files
```
frontend/src/
├── components/
│   └── InvoiceForm.tsx (new - invoice form tab/page)
├── pages/
│   ├── SettingsPage.tsx (new - main settings page)
│   └── QuickBooksSettingsPage.tsx (new - QB settings)
├── services/
│   ├── settingsApi.ts (new)
│   ├── invoiceApi.ts (new)
│   └── qbCustomerApi.ts (new)
└── types/
    └── index.ts (extend existing)
```

## Security
- Credentials encrypted at rest using Fernet encryption
- Encryption key from environment variable
- API responses mask sensitive fields (show only last 4 chars)
- Input validation on all user inputs
- Error messages don't expose sensitive information

