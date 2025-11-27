"""
QuickBooks Client Module

Provides a client for interacting with the QuickBooks Online API.
Handles authentication, API requests, and entity management.
"""

import os
import time
import base64
import requests
from typing import Dict, Any, List, Optional

# Safe modern minorversion for QBO API
MINOR_VERSION = "70"


class QuickBooksClient:
    """
    Client for interacting with QuickBooks Online API.
    
    Handles:
    - Authentication via OAuth2 refresh tokens
    - API requests with error handling and rate limiting
    - Entity lookups and creation (customers, items, terms, invoices)
    """
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, realm_id: str, 
                 environment: str = "production"):
        """
        Initialize QuickBooks client with authentication credentials.
        
        Args:
            client_id: QuickBooks OAuth2 client ID
            client_secret: QuickBooks OAuth2 client secret
            refresh_token: OAuth2 refresh token
            realm_id: QuickBooks company ID
            environment: "production" or "sandbox"
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.realm_id = realm_id
        self.environment = environment.lower().strip()
        self._access_token = None
        
    @classmethod
    def from_env(cls) -> 'QuickBooksClient':
        """
        Create a QuickBooks client from environment variables.
        
        Required env vars:
            QBO_CLIENT_ID
            QBO_CLIENT_SECRET
            QBO_REFRESH_TOKEN
            QBO_REALM_ID
            
        Optional env vars:
            QBO_ENV: "production" or "sandbox" (default: production)
            
        Returns:
            QuickBooksClient instance
            
        Raises:
            RuntimeError: If required env vars are missing
        """
        client_id = cls._env("QBO_CLIENT_ID", required=True)
        client_secret = cls._env("QBO_CLIENT_SECRET", required=True)
        refresh_token = cls._env("QBO_REFRESH_TOKEN", required=True)
        realm_id = cls._env("QBO_REALM_ID", required=True)
        environment = cls._env("QBO_ENV", default="production")
        
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            realm_id=realm_id,
            environment=environment
        )
    
    @staticmethod
    def _env(name: str, default: str = None, required: bool = False) -> str:
        """Get environment variable with validation"""
        v = os.getenv(name, default)
        if required and not v:
            raise RuntimeError(f"Missing required env var: {name}")
        return v
    
    @property
    def base_url(self) -> str:
        """Get the base URL for QuickBooks API based on environment"""
        if self.environment == "sandbox":
            return "https://sandbox-quickbooks.api.intuit.com"
        return "https://quickbooks.api.intuit.com"
    
    @property
    def access_token(self) -> str:
        """
        Get a valid access token, refreshing if needed.
        
        Returns:
            Valid OAuth2 access token
            
        Raises:
            RuntimeError: If token refresh fails
        """
        if not self._access_token:
            self._access_token = self._get_access_token()
        return self._access_token
    
    def _get_access_token(self) -> str:
        """
        Get a fresh access token using the refresh token.
        
        Returns:
            OAuth2 access token
            
        Raises:
            RuntimeError: If token refresh fails
        """
        url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        r = requests.post(url, headers=headers, data=data, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to refresh token: {r.status_code} {r.text}")
        j = r.json()
        # Note: Intuit may rotate refresh_token. If returned, persist it yourself.
        return j["access_token"]
    
    def request(self, method: str, path: str, params: Dict = None, json_body: Dict = None) -> Dict:
        """
        Make a request to the QuickBooks API with automatic retry for rate limits.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (e.g., "/customer")
            params: Query parameters
            json_body: Request body as JSON
            
        Returns:
            Response JSON
            
        Raises:
            RuntimeError: If API request fails
        """
        url = f"{self.base_url}/v3/company/{self.realm_id}{path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if params is None:
            params = {}
        params["minorversion"] = MINOR_VERSION
        
        r = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=60)
        
        # Handle rate limiting with retry
        if r.status_code == 429:
            time.sleep(2)
            r = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=60)
            
        if r.status_code >= 400:
            raise RuntimeError(f"QBO API error {r.status_code}: {r.text}")
            
        return r.json()
    
    def query(self, query_str: str) -> Dict:
        """
        Execute a QuickBooks SQL-like query.
        
        Args:
            query_str: QuickBooks query string
            
        Returns:
            Query response JSON
            
        Raises:
            RuntimeError: If query fails
        """
        url = f"{self.base_url}/v3/company/{self.realm_id}/query"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text",  # Intuit accepts text/plain or application/text
        }
        params = {"minorversion": MINOR_VERSION}
        
        r = requests.post(url, headers=headers, params=params, data=query_str, timeout=60)
        
        if r.status_code >= 400:
            raise RuntimeError(f"QBO Query error {r.status_code}: {r.text}")
            
        return r.json()
    
    # ---------- Entity lookups/ensures ----------
    def find_customer_by_display_name(self, name: str) -> Optional[Dict]:
        """
        Find a customer by display name.
        
        Args:
            name: Customer display name
            
        Returns:
            Customer data or None if not found
        """
        safe_name = name.replace("'", "''")
        q = f"select * from Customer where DisplayName = '{safe_name}'"
        res = self.query(q)
        cust = res.get("QueryResponse", {}).get("Customer", [])
        return cust[0] if cust else None
    
    def create_customer_minimal(self, display_name: str) -> Dict:
        """
        Create a minimal customer record.
        
        Args:
            display_name: Customer display name
            
        Returns:
            Created customer data
        """
        body = {"DisplayName": display_name}
        res = self.request("POST", "/customer", json_body=body)
        return res["Customer"]
    
    def ensure_customer(self, display_name: str) -> Dict:
        """
        Find or create a customer by display name.
        
        Args:
            display_name: Customer display name
            
        Returns:
            Customer reference object with value (ID) and name
        """
        cust = self.find_customer_by_display_name(display_name)
        if cust:
            return {"value": cust["Id"], "name": cust.get("DisplayName", display_name)}
        created = self.create_customer_minimal(display_name)
        return {"value": created["Id"], "name": created.get("DisplayName", display_name)}
    
    def find_item_by_name(self, name: str) -> Optional[Dict]:
        """
        Find an item by name.
        
        Args:
            name: Item name
            
        Returns:
            Item data or None if not found
        """
        safe_name = name.replace("'", "''")
        q = f"select * from Item where Name = '{safe_name}'"
        res = self.query(q)
        items = res.get("QueryResponse", {}).get("Item", [])
        return items[0] if items else None
    
    def find_income_account_ref(self) -> Dict:
        """
        Find an income account to use for items.
        
        Returns:
            Income account reference
            
        Raises:
            RuntimeError: If no income accounts found
        """
        q = "select Id, Name, AccountType from Account where AccountType = 'Income' order by Id asc"
        res = self.query(q)
        accts = res.get("QueryResponse", {}).get("Account", [])
        if not accts:
            raise RuntimeError("No Income accounts found. Please provide an IncomeAccountRef.")
        # Return first income account
        acct = accts[0]
        return {"value": acct["Id"], "name": acct.get("Name")}
    
    def create_service_item(self, name: str, taxable: bool = False, 
                           income_account_ref: Dict = None) -> Dict:
        """
        Create a service item.
        
        Args:
            name: Item name
            taxable: Whether item is taxable
            income_account_ref: Income account reference (found automatically if None)
            
        Returns:
            Created item data
        """
        if income_account_ref is None:
            income_account_ref = self.find_income_account_ref()
        body = {
            "Name": name,
            "Type": "Service",
            "IncomeAccountRef": income_account_ref,
            "Taxable": bool(taxable),
        }
        res = self.request("POST", "/item", json_body=body)
        return res["Item"]
    
    def ensure_item(self, name: str, taxable: bool = False) -> Dict:
        """
        Find or create an item by name.
        
        Args:
            name: Item name
            taxable: Whether item is taxable (used if creating)
            
        Returns:
            Item reference object with value (ID) and name
        """
        it = self.find_item_by_name(name)
        if it:
            return {"value": it["Id"], "name": it.get("Name", name)}
        created = self.create_service_item(name, taxable=taxable)
        return {"value": created["Id"], "name": created.get("Name", name)}
    
    def find_term_by_name(self, name: str) -> Optional[Dict]:
        """
        Find a sales term by name.
        
        Args:
            name: Term name (e.g., "Net 15")
            
        Returns:
            Term data or None if not found
        """
        safe_name = name.replace("'", "''")
        q = f"select Id, Name from Term where Name = '{safe_name}'"
        res = self.query(q)
        terms = res.get("QueryResponse", {}).get("Term", [])
        return terms[0] if terms else None
    
    def ensure_sales_term_ref(self, terms_name: str) -> Optional[Dict]:
        """
        Find a sales term by name or create a reference to it.
        
        Args:
            terms_name: Term name (e.g., "Net 15")
            
        Returns:
            Term reference object or None if terms_name is empty
        """
        if not terms_name:
            return None
        term = self.find_term_by_name(terms_name)
        if term:
            return {"value": term["Id"], "name": term.get("Name")}
        # If not found, let QBO ignore; many orgs have named terms (e.g., "Net 15") already present.
        return {"name": terms_name}
    
    def find_invoice_by_docnumber(self, docnumber: str) -> Optional[Dict]:
        """
        Find an invoice by document number.
        
        Args:
            docnumber: Invoice document number
            
        Returns:
            Invoice data or None if not found
        """
        safe_doc = docnumber.replace("'", "''")
        q = f"select Id, DocNumber, TxnDate, TotalAmt, Balance, EmailStatus from Invoice where DocNumber = '{safe_doc}'"
        res = self.query(q)
        invs = res.get("QueryResponse", {}).get("Invoice", [])
        return invs[0] if invs else None
    
    def get_invoice_status(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get invoice status information (EmailStatus, Balance) from QuickBooks.
        
        Args:
            invoice_id: QuickBooks invoice ID
            
        Returns:
            Dictionary with status info: {"email_status": str, "balance": float, "total_amount": float}
            or None if invoice not found
        """
        safe_id = invoice_id.replace("'", "''")
        q = f"select Id, DocNumber, EmailStatus, Balance, TotalAmt from Invoice where Id = '{safe_id}'"
        try:
            res = self.query(q)
            invs = res.get("QueryResponse", {}).get("Invoice", [])
            if not invs:
                return None
            
            invoice = invs[0] if isinstance(invs, list) else invs
            return {
                "email_status": invoice.get("EmailStatus"),
                "balance": float(invoice.get("Balance", 0)),
                "total_amount": float(invoice.get("TotalAmt", 0))
            }
        except Exception as e:
            print(f"Error getting invoice status: {e}")
            return None
    
    def find_last_invoice_for_customer(self, customer_id: str) -> Optional[Dict]:
        """
        Find the most recent invoice for a customer, ordered by creation date.
        
        Args:
            customer_id: QuickBooks customer ID
            
        Returns:
            Most recent invoice data or None if no invoices found
        """
        safe_id = customer_id.replace("'", "''")
        # Query invoices for this customer, ordered by TxnDate descending, limit 1
        # QuickBooks query syntax: orderby field desc maxresults n
        q = f"select Id, DocNumber, TxnDate, TotalAmt from Invoice where CustomerRef = '{safe_id}' orderby TxnDate desc maxresults 1"
        try:
            res = self.query(q)
            invs = res.get("QueryResponse", {}).get("Invoice", [])
            # Handle single dict vs list
            if isinstance(invs, dict):
                return invs
            return invs[0] if invs else None
        except Exception as e:
            # If query fails (e.g., no invoices), return None
            print(f"Error finding last invoice: {e}")
            return None
    
    def invoice_number_exists(self, docnumber: str) -> bool:
        """
        Check if an invoice with the given document number already exists.
        
        Args:
            docnumber: Invoice document number to check
            
        Returns:
            True if invoice exists, False otherwise
        """
        return self.find_invoice_by_docnumber(docnumber) is not None
    
    def build_invoice_body(self, customer_ref: Dict, doc_number: str, invoice_date: str, 
                          due_date: str, term_ref: Dict, line_objects: List[Dict]) -> Dict:
        """
        Build an invoice request body.
        
        Args:
            customer_ref: Customer reference object
            doc_number: Invoice document number
            invoice_date: Invoice date (YYYY-MM-DD)
            due_date: Due date (YYYY-MM-DD)
            term_ref: Term reference object
            line_objects: List of line item objects
            
        Returns:
            Invoice request body
        """
        body = {
            "CustomerRef": {"value": customer_ref["value"], "name": customer_ref.get("name")},
            "DocNumber": doc_number,     # QBO enforces uniqueness
            "TxnDate": invoice_date,     # "YYYY-MM-DD"
            "Line": line_objects,
        }
        if term_ref:
            # Prefer Id if we have it; QBO will ignore unknown names
            if "value" in term_ref:
                body["SalesTermRef"] = {"value": term_ref["value"], "name": term_ref.get("name")}
            else:
                body["SalesTermRef"] = {"name": term_ref.get("name")}
        if due_date:
            body["DueDate"] = due_date
        return body
    
    def create_invoice(self, invoice_body: Dict) -> Dict:
        """
        Create an invoice.
        
        Args:
            invoice_body: Invoice request body
            
        Returns:
            Created invoice data
        """
        res = self.request("POST", "/invoice", json_body=invoice_body)
        return res["Invoice"]