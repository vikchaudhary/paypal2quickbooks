# Gmail PO Fetching Integration Plan

## Overview

Connect to Gmail inbox via OAuth2, search for emails with PDF attachments, filter by original sender domain matching QuickBooks customers, and automatically download PDFs to the PO directory.

## Backend Implementation

### 1. Gmail Client Service

**File**: `backend/src/beanscounter/integrations/gmail_client.py` (new)

- Gmail API client using `google-auth` and `google-api-python-client`
- OAuth2 flow handling (authorization URL generation, token exchange)
- Email search with date filtering
- PDF attachment extraction and download
- Email header parsing to identify original sender (from forwarded emails)

Key methods:
- `get_authorization_url()` - Generate OAuth2 authorization URL
- `exchange_code_for_tokens(code: str)` - Exchange authorization code for tokens
- `search_emails(start_date: datetime, query: str = None)` - Search emails from date
- `get_email_details(email_id: str)` - Get full email details including headers
- `download_attachment(email_id: str, attachment_id: str, filename: str)` - Download attachment
- `extract_original_sender(email_data: Dict)` - Parse headers to find original sender domain

### 2. Gmail Settings Service

**File**: `backend/src/beanscounter/services/gmail_settings_service.py` (new)

- Similar to `settings_service.py` for QuickBooks
- Store encrypted Gmail credentials (access_token, refresh_token)
- Store sync settings (starting_date)
- Functions:
  - `save_gmail_credentials(access_token: str, refresh_token: str)`
  - `get_gmail_credentials() -> Optional[Dict]`
  - `has_gmail_credentials() -> bool`
  - `delete_gmail_credentials()`
  - `save_gmail_starting_date(date: str)` - Store starting date (ISO format)
  - `get_gmail_starting_date() -> Optional[str]`
  - `test_gmail_connection() -> Dict[str, Any]`

### 3. Email Domain Matching Service

**File**: `backend/src/beanscounter/services/email_domain_matching_service.py` (new)

- Match email sender domains to QuickBooks customer domains
- Functions:
  - `get_qb_customer_domains() -> Set[str]` - Fetch all QuickBooks customer email domains
  - `extract_sender_domain(email_data: Dict) -> Optional[str]` - Extract domain from original sender
  - `matches_qb_customer(sender_domain: str) -> bool` - Check if domain matches any QB customer

### 4. Gmail Sync Service

**File**: `backend/src/beanscounter/services/gmail_sync_service.py` (new)

- Orchestrate email fetching and PDF download
- Functions:
  - `sync_emails_from_gmail(start_date: Optional[datetime] = None) -> Dict[str, Any]`
    - Search emails from starting date
    - Filter emails with PDF attachments
    - Extract original sender domain
    - Match against QuickBooks customer domains
    - Download matching PDFs to PO directory
    - Return sync results (emails processed, PDFs downloaded, errors)

### 5. Gmail API Router

**File**: `backend/src/beanscounter/api/routers/gmail.py` (new)

Endpoints:
- `GET /gmail/authorize` - Get OAuth2 authorization URL
- `POST /gmail/oauth/callback` - Handle OAuth2 callback, exchange code for tokens
- `GET /gmail/settings` - Get Gmail settings (configured status, starting date)
- `POST /gmail/settings` - Save Gmail settings (starting date)
- `POST /gmail/settings/credentials` - Save Gmail credentials (after OAuth)
- `DELETE /gmail/settings` - Delete Gmail configuration
- `POST /gmail/test` - Test Gmail connection
- `POST /gmail/sync` - Manual sync trigger (fetch emails and download PDFs)
- `GET /gmail/sync/status` - Get last sync status/results

### 6. Update Settings Router

**File**: `backend/src/beanscounter/api/routers/settings.py` (modify)

- Add Gmail settings endpoints (or keep them in gmail.py router)
- Register gmail router in `app.py`

### 7. Update App Router

**File**: `backend/src/beanscounter/api/app.py` (modify)

- Register Gmail router: `app.include_router(gmail_router)`

### 8. Dependencies

**File**: `backend/requirements.txt` (modify)

Add:
```
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-api-python-client>=2.100.0
```

## Frontend Implementation

### 1. Gmail Settings Page

**File**: `frontend/src/pages/GmailSettingsPage.jsx` (new)

- OAuth2 authorization button ("Connect to Gmail")
- Starting date picker (date input)
- Connection status display
- Test connection button
- Delete configuration button
- Display last sync status
- Manual sync button

UI similar to `QuickBooksSettingsPage.jsx`:
- Show authorization URL or "Connected" status
- Input field for starting date
- Save/Test/Delete buttons

### 2. Update Settings Page

**File**: `frontend/src/pages/SettingsPage.jsx` (modify)

- Add "Gmail" section to sidebar navigation
- Render `GmailSettingsPage` when Gmail section is active

### 3. Gmail API Service

**File**: `frontend/src/services/gmailApi.js` (new)

Functions:
- `getGmailAuthUrl()` - Get OAuth2 authorization URL
- `saveGmailCredentials(code: string)` - Exchange code and save credentials
- `getGmailSettings()` - Get Gmail settings
- `saveGmailSettings(settings)` - Save settings (starting date)
- `deleteGmailSettings()` - Delete configuration
- `testGmailConnection()` - Test connection
- `syncGmailEmails()` - Trigger manual sync
- `getGmailSyncStatus()` - Get last sync status

### 4. Update PO List View

**File**: `frontend/src/components/POList.jsx` (modify)

- Add "Sync Gmail" button at top of PO list (if Gmail is configured)
- Show sync status/progress when syncing
- Refresh PO list after successful sync

### 5. OAuth2 Callback Handling

**File**: `frontend/src/App.jsx` or new callback route (modify)

- Handle OAuth2 redirect callback
- Extract authorization code from URL
- Call API to exchange code for tokens
- Redirect to Settings page

## Email Filtering Logic

### 1. Email Search Query

Gmail API query:
```
has:attachment filename:pdf after:{start_date}
```

### 2. Original Sender Extraction

For forwarded emails, check email headers:
- `X-Original-From` header
- `From` header (if not from indianbento.com)
- `Reply-To` header
- Parse email body for "From:" or "Original Message" patterns

### 3. Domain Matching

- Extract domain from original sender email
- Normalize domain (lowercase, remove www)
- Fetch all QuickBooks customers with email addresses
- Extract domains from customer emails (`PrimaryEmailAddr.Address`)
- Match sender domain against QB customer domains
- If match found, download PDF attachment

### 4. PDF Download

- Download PDF to `backend/data/pos/` directory
- Filename format: `PO_{customer_name}_{po_number}_{MM-DD-YYYY}.pdf` -- look up the customer_name using the original email address, and check email subject and body if it contains PO number
- Ensure unique filenames (handle duplicates)

## Data Storage

### 1. Gmail Credentials

**File**: `backend/data/settings.json` (extend)

Add `gmail` section:
```json
{
  "gmail": {
    "access_token": "<encrypted>",
    "refresh_token": "<encrypted>",
    "starting_date": "2024-01-01"
  }
}
```

### 2. Sync History (Optional)

**File**: `backend/data/gmail_sync_history.json` (new)

Track sync operations:
```json
{
  "last_sync": "2024-11-26T10:00:00",
  "emails_processed": 10,
  "pdfs_downloaded": 5,
  "errors": []
}
```

## OAuth2 Flow

1. User clicks "Connect to Gmail" in Settings
2. Frontend calls `GET /gmail/authorize`
3. Backend generates OAuth2 authorization URL
4. User redirected to Google OAuth consent screen
5. User grants permissions
6. Google redirects to callback URL with authorization code
7. Frontend calls `POST /gmail/oauth/callback` with code
8. Backend exchanges code for access/refresh tokens
9. Tokens encrypted and stored in settings.json
10. Connection status updated

## Gmail API Scopes Required

- `https://www.googleapis.com/auth/gmail.readonly` - Read emails and attachments

## Error Handling

- Handle OAuth2 errors (user denied, expired tokens)
- Handle API rate limits
- Handle attachment download failures
- Log errors but continue processing other emails
- Return detailed sync results with success/error counts

## Files to Create

**Backend**:
- `backend/src/beanscounter/integrations/gmail_client.py`
- `backend/src/beanscounter/services/gmail_settings_service.py`
- `backend/src/beanscounter/services/email_domain_matching_service.py`
- `backend/src/beanscounter/services/gmail_sync_service.py`
- `backend/src/beanscounter/api/routers/gmail.py`

**Frontend**:
- `frontend/src/pages/GmailSettingsPage.jsx`
- `frontend/src/services/gmailApi.js`

## Files to Modify

**Backend**:
- `backend/requirements.txt` - Add Google API libraries
- `backend/src/beanscounter/api/app.py` - Register Gmail router
- `backend/src/beanscounter/api/routers/settings.py` - Optional: add Gmail endpoints here instead

**Frontend**:
- `frontend/src/pages/SettingsPage.jsx` - Add Gmail section
- `frontend/src/components/POList.jsx` - Add sync button
- `frontend/src/App.jsx` - Handle OAuth callback (if needed)

## Configuration

### Google Cloud Console Setup

User needs to:
1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth2 credentials (Client ID, Client Secret)
4. Configure redirect URI (e.g., `http://localhost:5173/gmail/callback`)

### Environment Variables (Optional)

- `GMAIL_CLIENT_ID` - OAuth2 client ID
- `GMAIL_CLIENT_SECRET` - OAuth2 client secret
- `GMAIL_REDIRECT_URI` - OAuth2 redirect URI

Or store in settings.json (encrypted) after initial setup.

## Testing Considerations

- Test with forwarded emails from indianbento.com
- Test with emails from various customer domains
- Test with multiple PDF attachments
- Test with emails without matching customer domains
- Test OAuth2 flow (authorization, token refresh)
- Test error scenarios (API failures, invalid tokens)

