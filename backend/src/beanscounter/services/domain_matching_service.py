"""
Domain Matching Service
Matches email domains to company names using QuickBooks and heuristics.
"""

from typing import Optional
from beanscounter.core.domain_utils import extract_domain, normalize_domain, domain_to_company_name
from beanscounter.services.qb_customer_service import search_customers_by_domain, _get_qb_client
from beanscounter.integrations.quickbooks_client import QuickBooksClient


def match_domain_to_company(domain: str, qb_client: Optional[QuickBooksClient] = None) -> Optional[str]:
    """
    Match domain to company name using QuickBooks search and heuristics.
    
    Args:
        domain: Email domain (e.g., "acme.com")
        qb_client: Optional QuickBooks client (if None, will create one)
        
    Returns:
        Company name if found, None otherwise
    """
    if not domain:
        return None
    
    normalized_domain = normalize_domain(domain)
    
    # Try QuickBooks search first
    try:
        if qb_client is None:
            # Try to get QB client, but don't fail if not configured
            try:
                qb_client = _get_qb_client()
            except Exception:
                qb_client = None
        
        if qb_client:
            customers = search_customers_by_domain(normalized_domain)
            
            if customers:
                # If multiple matches, prefer company name over display name
                # and prefer the first match (could be enhanced to pick most recent)
                for customer in customers:
                    if customer.get("company_name"):
                        return customer["company_name"]
                    if customer.get("display_name"):
                        return customer["display_name"]
                    if customer.get("name"):
                        return customer["name"]
    except Exception as e:
        # If QB search fails, continue to heuristic fallback
        print(f"QuickBooks domain search failed: {e}")
    
    # Fallback to heuristic conversion
    company_name = domain_to_company_name(normalized_domain)
    return company_name if company_name else None


def get_company_name_from_email(email: str, qb_client: Optional[QuickBooksClient] = None) -> Optional[str]:
    """
    Extract company name from email address.
    
    Main entry point: extract domain → match to company.
    
    Args:
        email: Email address (e.g., "user@acme.com")
        qb_client: Optional QuickBooks client
        
    Returns:
        Company name if found, None otherwise
    """
    if not email:
        return None
    
    # Extract domain from email
    domain = extract_domain(email)
    if not domain:
        return None
    
    # Match domain to company
    return match_domain_to_company(domain, qb_client)

