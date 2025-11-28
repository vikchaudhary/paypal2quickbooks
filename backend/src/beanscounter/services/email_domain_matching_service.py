"""
Email Domain Matching Service
Matches email sender domains to QuickBooks customer domains.
"""

from typing import Set, Optional, Dict, Any
from beanscounter.core.domain_utils import extract_domain, normalize_domain
from beanscounter.services.qb_customer_service import search_customers_by_domain


def get_qb_customer_domains() -> Set[str]:
    """
    Fetch all QuickBooks customer email domains.
    
    Returns:
        Set of normalized email domains from QuickBooks customers
    """
    try:
        from beanscounter.services.settings_service import get_qb_credentials
        from beanscounter.integrations.quickbooks_client import QuickBooksClient
        
        credentials = get_qb_credentials()
        if not credentials:
            return set()
        
        qb_client = QuickBooksClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            realm_id=credentials["realm_id"],
            environment=credentials["environment"]
        )
        
        # Query all customers with email addresses
        # Note: QuickBooks API may return maxResults, so we need to handle pagination
        all_customers = []
        max_results = 1000  # QuickBooks default max
        start_position = 1
        
        while True:
            try:
                query = f"select PrimaryEmailAddr, WebAddr from Customer maxresults {max_results} startposition {start_position}"
                result = qb_client.query(query)
                query_response = result.get("QueryResponse", {})
                customers_raw = query_response.get("Customer", [])
                
                # Handle single dict vs list
                if isinstance(customers_raw, dict):
                    all_customers.append(customers_raw)
                elif isinstance(customers_raw, list):
                    all_customers.extend(customers_raw)
                else:
                    # No customers returned
                    break
                
                # Check if there are more results
                # If customers_raw is a list, check its length
                if isinstance(customers_raw, list):
                    num_returned = len(customers_raw)
                else:
                    num_returned = 1 if customers_raw else 0
                
                max_results_returned = query_response.get("maxResults", num_returned)
                
                # If no customers returned, we're done
                if not customers_raw:
                    break
                
                # If we got a single dict, we're done (no pagination needed)
                if isinstance(customers_raw, dict):
                    break
                
                # If we got fewer than requested, we're done
                if num_returned < max_results_returned:
                    break
                
                # If we got exactly what we asked for, there might be more
                start_position += num_returned
            except Exception as e:
                print(f"Error querying customers (page {start_position}): {e}")
                # If this is the first page and it fails, we might have a syntax issue
                # Try without pagination parameters as fallback
                if start_position == 1:
                    try:
                        query = "select PrimaryEmailAddr, WebAddr from Customer"
                        result = qb_client.query(query)
                        query_response = result.get("QueryResponse", {})
                        customers_raw = query_response.get("Customer", [])
                        if isinstance(customers_raw, dict):
                            all_customers.append(customers_raw)
                        elif isinstance(customers_raw, list):
                            all_customers.extend(customers_raw)
                    except Exception as e2:
                        print(f"Error with fallback query: {e2}")
                break
        
        domains = set()
        for cust in all_customers:
            # Extract domain from PrimaryEmailAddr
            email_addr = cust.get("PrimaryEmailAddr", {})
            if isinstance(email_addr, dict):
                email = email_addr.get("Address", "")
                if email:
                    domain = extract_domain(email)
                    if domain:
                        normalized = normalize_domain(domain)
                        if normalized:
                            domains.add(normalized)
            
            # Also check WebAddr for domain matching
            web_addr = cust.get("WebAddr", {})
            if isinstance(web_addr, dict):
                url = web_addr.get("URI", "")
                if url:
                    # Extract domain from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    if parsed.netloc:
                        domain = normalize_domain(parsed.netloc)
                        if domain:
                            domains.add(domain)
        
        print(f"DEBUG: Found {len(all_customers)} customers, extracted {len(domains)} unique domains")
        return domains
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error fetching QB customer domains: {e}")
        
        # Check if it's an authentication error
        if "invalid_grant" in error_msg or "refresh token" in error_msg.lower() or "invalid token" in error_msg.lower():
            print("WARNING: QuickBooks authentication failed. The refresh token may be expired or invalid.")
            print("Please reauthorize QuickBooks in the Settings page.")
        
        print(f"Traceback: {traceback.format_exc()}")
        return set()


def extract_sender_domain(email_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract domain from original sender email.
    Handles forwarded emails by checking various headers.
    
    Args:
        email_data: Email data from Gmail API (includes headers)
        
    Returns:
        Normalized sender domain or None if not found
    """
    headers = email_data.get("payload", {}).get("headers", [])
    
    # Build a dict from headers for easier lookup
    header_dict = {}
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        header_dict[name] = value
    
    # Priority order for finding original sender:
    # 1. X-Original-From (common in forwarded emails)
    # 2. From (if not from indianbento.com)
    # 3. Reply-To
    # 4. Parse email body for "From:" patterns
    
    sender_email = None
    
    # Check X-Original-From
    if "x-original-from" in header_dict:
        sender_email = header_dict["x-original-from"]
    # Check From header (if not from indianbento.com)
    elif "from" in header_dict:
        from_header = header_dict["from"]
        if "indianbento.com" not in from_header.lower():
            sender_email = from_header
    # Check Reply-To
    elif "reply-to" in header_dict:
        sender_email = header_dict["reply-to"]
    
    # Extract email address from header value (may contain name <email>)
    if sender_email:
        import re
        # Pattern to match email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, sender_email)
        if matches:
            sender_email = matches[0]
    
    # If still no sender found, try parsing email body
    if not sender_email:
        body = email_data.get("snippet", "") or ""
        # Look for "From:" patterns in body
        from_pattern = r'From:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
        matches = re.findall(from_pattern, body, re.IGNORECASE)
        if matches:
            sender_email = matches[0]
    
    if sender_email:
        domain = extract_domain(sender_email)
        if domain:
            return normalize_domain(domain)
    
    return None


def matches_qb_customer(sender_domain: str) -> bool:
    """
    Check if sender domain matches any QuickBooks customer domain.
    
    Uses search_customers_by_domain for more robust matching that checks
    both email addresses and web addresses.
    
    Args:
        sender_domain: Normalized sender domain
        
    Returns:
        True if domain matches a QB customer, False otherwise
    """
    if not sender_domain:
        return False
    
    normalized_sender = normalize_domain(sender_domain)
    
    # Use search_customers_by_domain which checks both PrimaryEmailAddr and WebAddr
    # This is more reliable than just checking the cached domain set
    try:
        customers = search_customers_by_domain(normalized_sender)
        return len(customers) > 0
    except Exception as e:
        print(f"Error checking QB customer match for domain {normalized_sender}: {e}")
        # Fallback to domain set check
        qb_domains = get_qb_customer_domains()
        return normalized_sender in qb_domains


def get_customer_name_from_email(email: str) -> Optional[str]:
    """
    Get QuickBooks customer name from email address.
    
    Args:
        email: Email address
        
    Returns:
        Customer display name or None if not found
    """
    domain = extract_domain(email)
    if not domain:
        return None
    
    normalized_domain = normalize_domain(domain)
    customers = search_customers_by_domain(normalized_domain)
    
    if customers:
        # Return the first matching customer's display name
        return customers[0].get("display_name") or customers[0].get("name")
    
    return None

