"""
Domain Utilities
Functions for extracting and normalizing email domains.
"""

import re
from typing import Optional


def extract_domain(email: str) -> Optional[str]:
    """
    Extract domain from email address.
    
    Args:
        email: Email address (e.g., "user@acme.com")
        
    Returns:
        Domain string (e.g., "acme.com") or None if invalid
    """
    if not email or not isinstance(email, str):
        return None
    
    # Basic email validation and domain extraction
    email_pattern = r'^[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})$'
    match = re.match(email_pattern, email.strip())
    
    if match:
        return match.group(1)
    
    return None


def normalize_domain(domain: str) -> str:
    """
    Normalize domain string (lowercase, remove www).
    
    Args:
        domain: Domain string (e.g., "WWW.Acme.COM")
        
    Returns:
        Normalized domain (e.g., "acme.com")
    """
    if not domain:
        return ""
    
    domain = domain.lower().strip()
    
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    
    return domain


def domain_to_company_name(domain: str) -> str:
    """
    Convert domain to company name using simple heuristics.
    
    Args:
        domain: Domain string (e.g., "acme-corp.com")
        
    Returns:
        Company name (e.g., "Acme Corp")
    """
    if not domain:
        return ""
    
    # Normalize domain
    domain = normalize_domain(domain)
    
    # Remove TLD (last part after final dot)
    parts = domain.split('.')
    if len(parts) > 1:
        # Remove TLD
        domain_part = '.'.join(parts[:-1])
    else:
        domain_part = domain
    
    # Split on hyphens and dots
    words = re.split(r'[-.]', domain_part)
    
    # Capitalize each word
    capitalized_words = []
    for word in words:
        if word:
            # Capitalize first letter, lowercase rest
            capitalized = word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper()
            capitalized_words.append(capitalized)
    
    # Join words with space
    company_name = ' '.join(capitalized_words)
    
    return company_name

