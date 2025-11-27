# Domain to Company Name Matching Plan

## Overview
When a PO is missing a customer name but has a customer email, extract the domain and match it to a company name using QuickBooks customer search and heuristics.

## Approach
Use a hybrid matching strategy:
1. **Extract domain** from email (e.g., "john@acme.com" → "acme.com")
2. **Search QuickBooks customers** by domain (check email fields in customer records)
3. **Simple heuristics** as fallback (e.g., "acme.com" → "Acme")
4. **Optional local cache** for manual domain→company mappings

## Implementation

### Backend Changes

#### 1. Domain Extraction Utility
**File**: `backend/src/beanscounter/core/domain_utils.py` (new)
- `extract_domain(email: str) -> Optional[str]` - Extract domain from email
- `normalize_domain(domain: str) -> str` - Normalize domain (lowercase, remove www)
- `domain_to_company_name(domain: str) -> str` - Simple heuristic conversion
  - Examples: "acme.com" → "Acme", "acme-corp.com" → "Acme Corp"

#### 2. QuickBooks Customer Domain Search
**File**: `backend/src/beanscounter/services/qb_customer_service.py` (extend)
- `search_customers_by_domain(domain: str) -> List[Dict]` - Search customers by email domain
  - Query QuickBooks: `select * from Customer where PrimaryEmailAddr.Address like '%@domain.com'`
  - Returns matching customers

#### 3. Domain Matching Service
**File**: `backend/src/beanscounter/services/domain_matching_service.py` (new)
- `match_domain_to_company(domain: str, qb_client: QuickBooksClient) -> Optional[str]`
  - Search QuickBooks customers by domain
  - If multiple matches, return the most recent or most common
  - Fallback to heuristic conversion if no QB match
- `get_company_name_from_email(email: str, qb_client: Optional[QuickBooksClient] = None) -> Optional[str]`
  - Main entry point: extract domain → match to company

#### 4. PO Reader Integration
**File**: `backend/src/beanscounter/core/po_reader.py` (modify)
- In `_parse_text()` method, after extracting `customer_email`:
  - If `customer` is "Unknown" and `customer_email` exists:
    - Extract domain and attempt to match to company name
    - Set `customer` to matched name if found

#### 5. API Endpoint (Optional)
**File**: `backend/src/beanscounter/api/routers/invoices.py` (extend)
- `POST /invoices/suggest-company-from-email` - Manual suggestion endpoint
  - Request: `{ "email": "user@acme.com" }`
  - Response: `{ "suggested_name": "Acme", "source": "quickbooks" | "heuristic" }`

### Frontend Changes

#### 1. Company Name Suggestion Display
**File**: `frontend/src/components/PODetails.jsx` (modify)
- When `vendor_name` is "Unknown" but `customer_email` exists:
  - Show a suggestion banner/button: "Suggest company name from email domain"
  - On click, call API to get suggestion
  - Display suggested name with option to accept/reject

#### 2. API Service
**File**: `frontend/src/services/invoiceApi.js` (extend)
- `suggestCompanyFromEmail(email: string)` - Call suggestion endpoint

## Data Flow

1. **PO Extraction**:
   - Extract email → extract domain → search QB → heuristic fallback → set customer name

2. **Manual Suggestion** (if auto-match fails):
   - User clicks "Suggest from email" → API call → display suggestion → user accepts/rejects

## QuickBooks Query Strategy

Search customers by email domain:
```sql
select Id, DisplayName, CompanyName, PrimaryEmailAddr from Customer 
where PrimaryEmailAddr.Address like '%@acme.com'
```

Note: QuickBooks may not support direct email domain queries. Alternative:
- Fetch all customers (if small dataset) and filter in Python
- Or use a broader search and filter results

## Heuristic Rules

Simple domain-to-company conversion:
- Remove TLD (.com, .org, etc.)
- Split on hyphens/dots
- Capitalize words
- Examples:
  - "acme.com" → "Acme"
  - "acme-corp.com" → "Acme Corp"
  - "acme.inc.com" → "Acme Inc"

## Files to Create/Modify

**New Files**:
- `backend/src/beanscounter/core/domain_utils.py`
- `backend/src/beanscounter/services/domain_matching_service.py`

**Modified Files**:
- `backend/src/beanscounter/core/po_reader.py` - Add domain matching during extraction
- `backend/src/beanscounter/services/qb_customer_service.py` - Add domain search
- `backend/src/beanscounter/api/routers/invoices.py` - Optional suggestion endpoint
- `frontend/src/components/PODetails.jsx` - Show suggestion UI
- `frontend/src/services/invoiceApi.js` - Add suggestion API call

## Considerations

1. **QuickBooks API Limitations**: Email domain queries may not be directly supported. May need to fetch and filter.
2. **Performance**: If QB has many customers, domain search could be slow. Consider caching.
3. **Accuracy**: Heuristics are best-effort. Manual review recommended.
4. **Privacy**: Only use email domains, never full email addresses in logs/storage.

