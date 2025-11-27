"""
QuickBooks Customer Service
Provides functions to search and retrieve QuickBooks customers.
"""

from typing import List, Dict, Any, Optional
from beanscounter.services.settings_service import get_qb_credentials
from beanscounter.integrations.quickbooks_client import QuickBooksClient
from beanscounter.core.domain_utils import normalize_domain


def _get_qb_client() -> QuickBooksClient:
    """
    Get QuickBooks client instance using stored credentials.
    
    Returns:
        QuickBooksClient instance
        
    Raises:
        RuntimeError: If credentials not configured
    """
    credentials = get_qb_credentials()
    if not credentials:
        raise RuntimeError("QuickBooks credentials not configured")
    
    return QuickBooksClient(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        refresh_token=credentials["refresh_token"],
        realm_id=credentials["realm_id"],
        environment=credentials["environment"]
    )


def search_customers(search_term: str) -> List[Dict[str, Any]]:
    """
    Search QuickBooks customers by name.
    
    Args:
        search_term: Search term (customer name)
        
    Returns:
        List of customer dictionaries with id, name, display_name, etc.
        Empty list if no matches found
    """
    if not search_term or not search_term.strip():
        return []
    
    try:
        qb_client = _get_qb_client()
        
        # Escape single quotes for SQL query
        safe_term = search_term.replace("'", "''")
        
        # QuickBooks doesn't support multiple OR conditions in queries
        # Search each field separately and combine unique results
        all_customers = []
        seen_ids = set()
        
        # Search fields in order of importance: DisplayName, CompanyName, GivenName, FamilyName
        search_fields = [
            ("DisplayName", "DisplayName"),
            ("CompanyName", "CompanyName"),
            ("GivenName", "GivenName"),
            ("FamilyName", "FamilyName")
        ]
        
        for field_name, field_alias in search_fields:
            try:
                query = f"select Id, DisplayName, CompanyName, GivenName, FamilyName from Customer where {field_name} like '%{safe_term}%'"
                result = qb_client.query(query)
                customers_raw = result.get("QueryResponse", {}).get("Customer", [])
                
                # QuickBooks returns a single dict if one result, list if multiple
                if isinstance(customers_raw, dict):
                    field_customers = [customers_raw]
                else:
                    field_customers = customers_raw if isinstance(customers_raw, list) else []
                
                # Add unique customers (by ID) to results
                for cust in field_customers:
                    cust_id = cust.get("Id")
                    if cust_id and cust_id not in seen_ids:
                        seen_ids.add(cust_id)
                        all_customers.append(cust)
            except Exception as e:
                # If this field search fails, continue with next field
                print(f"Search in {field_name} failed: {e}")
                continue
        
        customers = all_customers
        
        # If no results and search term has multiple words, try a simpler approach:
        # Search for the longest significant words (likely to be unique identifiers)
        if not customers and len(search_term.strip().split()) > 1:
            words = [w for w in search_term.strip().split() if len(w) > 2]  # Only words longer than 2 chars
            # Sort by length (longest first) and take the top 2-3 words to avoid too many OR conditions
            words = sorted(words, key=len, reverse=True)[:3]
            
            if len(words) > 0:
                # Try searching for each significant word individually and combine results
                all_customers = []
                seen_ids = set()
                
                for word in words:
                    safe_word = word.replace("'", "''")
                    # Search for this word in DisplayName and CompanyName
                    query = f"select Id, DisplayName, CompanyName, GivenName, FamilyName from Customer where DisplayName like '%{safe_word}%' or CompanyName like '%{safe_word}%'"
                    try:
                        result = qb_client.query(query)
                        customers_raw = result.get("QueryResponse", {}).get("Customer", [])
                        # Handle single dict vs list
                        if isinstance(customers_raw, dict):
                            word_customers = [customers_raw]
                        else:
                            word_customers = customers_raw if isinstance(customers_raw, list) else []
                        
                        # Add unique customers (by ID) to results
                        for cust in word_customers:
                            cust_id = cust.get("Id")
                            if cust_id and cust_id not in seen_ids:
                                seen_ids.add(cust_id)
                                all_customers.append(cust)
                    except Exception as e:
                        # If this word search fails, continue with next word
                        print(f"Word search for '{word}' failed: {e}")
                        continue
                
                customers = all_customers
        
        # Normalize customer data
        normalized = []
        for cust in customers:
            normalized.append({
                "id": cust.get("Id"),
                "name": cust.get("DisplayName", ""),
                "display_name": cust.get("DisplayName", ""),
                "company_name": cust.get("CompanyName"),
                "given_name": cust.get("GivenName"),
                "family_name": cust.get("FamilyName")
            })
        
        return normalized
    except Exception as e:
        # Log error but return empty list
        print(f"Error searching customers: {e}")
        return []


def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get specific customer by ID.
    
    Args:
        customer_id: QuickBooks customer ID
        
    Returns:
        Customer dictionary or None if not found
    """
    if not customer_id:
        return None
    
    try:
        qb_client = _get_qb_client()
        
        # Escape single quotes
        safe_id = customer_id.replace("'", "''")
        query = f"select Id, DisplayName, CompanyName, GivenName, FamilyName from Customer where Id = '{safe_id}'"
        
        result = qb_client.query(query)
        customers = result.get("QueryResponse", {}).get("Customer", [])
        
        if not customers:
            return None
        
        cust = customers[0]
        return {
            "id": cust.get("Id"),
            "name": cust.get("DisplayName", ""),
            "display_name": cust.get("DisplayName", ""),
            "company_name": cust.get("CompanyName"),
            "given_name": cust.get("GivenName"),
            "family_name": cust.get("FamilyName")
        }
    except Exception as e:
        print(f"Error getting customer: {e}")
        return None


def search_customers_by_domain(domain: str) -> List[Dict[str, Any]]:
    """
    Search QuickBooks customers by email domain.
    
    Args:
        domain: Email domain (e.g., "acme.com")
        
    Returns:
        List of customer dictionaries matching the domain
        Empty list if no matches found
    """
    if not domain or not domain.strip():
        return []
    
    try:
        qb_client = _get_qb_client()
        
        # Normalize domain
        normalized_domain = normalize_domain(domain)
        
        # QuickBooks doesn't support direct email domain queries in WHERE clause
        # We need to fetch customers and filter by email domain
        # Use a broad query to get customers with email addresses
        query = "select Id, DisplayName, CompanyName, GivenName, FamilyName, PrimaryEmailAddr from Customer"
        
        try:
            result = qb_client.query(query)
            customers_raw = result.get("QueryResponse", {}).get("Customer", [])
            
            # Handle single dict vs list
            if isinstance(customers_raw, dict):
                all_customers = [customers_raw]
            else:
                all_customers = customers_raw if isinstance(customers_raw, list) else []
            
            # Filter customers by email domain
            matching_customers = []
            for cust in all_customers:
                email_addr = cust.get("PrimaryEmailAddr", {})
                if isinstance(email_addr, dict):
                    email = email_addr.get("Address", "")
                else:
                    email = ""
                
                if email and normalized_domain in normalize_domain(email):
                    matching_customers.append(cust)
            
            # Normalize customer data
            normalized = []
            for cust in matching_customers:
                normalized.append({
                    "id": cust.get("Id"),
                    "name": cust.get("DisplayName", ""),
                    "display_name": cust.get("DisplayName", ""),
                    "company_name": cust.get("CompanyName"),
                    "given_name": cust.get("GivenName"),
                    "family_name": cust.get("FamilyName"),
                    "email": cust.get("PrimaryEmailAddr", {}).get("Address") if isinstance(cust.get("PrimaryEmailAddr"), dict) else None
                })
            
            return normalized
        except Exception as e:
            # If query fails, return empty list
            print(f"Error querying customers: {e}")
            return []
    except Exception as e:
        print(f"Error searching customers by domain: {e}")
        return []

