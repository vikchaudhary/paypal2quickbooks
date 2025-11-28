"""
Gmail Sync Service
Orchestrates email fetching and PDF download from Gmail.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from beanscounter.integrations.gmail_client import GmailClient
from beanscounter.services.gmail_settings_service import (
    get_gmail_credentials, 
    get_gmail_starting_date,
    get_gmail_forwarding_email
)
from beanscounter.services.email_domain_matching_service import (
    extract_sender_domain,
    matches_qb_customer,
    get_customer_name_from_email
)
from beanscounter.core.domain_utils import extract_domain, normalize_domain


# PO directory (same as invoices router)
# backend/src/beanscounter/services/gmail_sync_service.py -> backend/data/pos
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
PO_DIR = BACKEND_ROOT / "data" / "pos"


def _ensure_po_dir():
    """Ensure PO directory exists."""
    PO_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters for filenames
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    return filename


def sync_emails_from_gmail(start_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Sync emails from Gmail, filter by customer domains, and download PDFs.
    
    Args:
        start_date: Start date for email search (defaults to saved starting_date)
        
    Returns:
        Dictionary with sync results:
        {
            "success": bool,
            "emails_processed": int,
            "pdfs_downloaded": int,
            "errors": List[str],
            "downloaded_files": List[str]
        }
    """
    _ensure_po_dir()
    
    result = {
        "success": True,
        "emails_processed": 0,
        "pdfs_downloaded": 0,
        "errors": [],
        "downloaded_files": [],
        "debug_info": {
            "skipped_reasons": {},
            "sample_sender_emails": [],
            "email_domains": {},  # domain -> count
            "qb_customer_domains": [],
            "matching_domains": [],
            "search_query": "",
            "email_debug": [],  # Failed emails
            "successful_emails": []  # Successfully processed emails
        }
    }
    
    try:
        # Check QuickBooks connection before proceeding
        from beanscounter.services.settings_service import test_qb_connection, has_qb_credentials
        if has_qb_credentials():
            qb_test = test_qb_connection()
            if not qb_test["success"]:
                result["success"] = False
                error_msg = qb_test.get("message", "QuickBooks connection failed")
                if "invalid_grant" in error_msg.lower() or "refresh token" in error_msg.lower():
                    result["errors"].append(
                        "QuickBooks authentication failed: The refresh token is expired or invalid. "
                        "Please reauthorize QuickBooks in Settings > QuickBooks."
                    )
                else:
                    result["errors"].append(f"QuickBooks connection failed: {error_msg}. Please check your QuickBooks settings.")
                return result
        # Get Gmail credentials
        credentials = get_gmail_credentials()
        if not credentials:
            result["success"] = False
            result["errors"].append("Gmail credentials not configured")
            return result
        
        # Get OAuth2 client credentials from settings
        from beanscounter.services.gmail_settings_service import get_gmail_oauth_credentials
        oauth_creds = get_gmail_oauth_credentials()
        
        if not oauth_creds:
            result["success"] = False
            result["errors"].append("Gmail OAuth2 credentials (client_id, client_secret) not configured")
            return result
        
        client_id = oauth_creds["client_id"]
        client_secret = oauth_creds["client_secret"]
        redirect_uri = oauth_creds.get("redirect_uri", "http://localhost:5173/gmail/callback")
        
        # Initialize Gmail client
        gmail_client = GmailClient(
            client_id=client_id,
            client_secret=client_secret,
            access_token=credentials["access_token"],
            refresh_token=credentials["refresh_token"],
            redirect_uri=redirect_uri
        )
        
        # Get start date
        if start_date is None:
            starting_date_str = get_gmail_starting_date()
            if starting_date_str:
                try:
                    start_date = datetime.fromisoformat(starting_date_str)
                except ValueError:
                    # Try parsing YYYY-MM-DD format
                    start_date = datetime.strptime(starting_date_str, "%Y-%m-%d")
            else:
                # Default to 30 days ago
                from datetime import timedelta
                start_date = datetime.now() - timedelta(days=30)
        
        # Build search query with forwarding email filter
        forwarding_email = get_gmail_forwarding_email()
        additional_query = None
        
        if forwarding_email:
            # Search for emails from the forwarding address in inbox with attachments
            # This matches: in:inbox has:attachment from:pashmina@indianbento.com after:YYYY/MM/DD
            additional_query = f"in:inbox has:attachment from:{forwarding_email}"
        else:
            # Default: search inbox with PDF attachments
            additional_query = "in:inbox has:attachment filename:pdf"
        
        # Search for emails
        email_ids = gmail_client.search_emails(start_date, query=additional_query)
        result["emails_processed"] = len(email_ids)
        
        # Log search query for debugging
        date_str = start_date.strftime('%Y/%m/%d')
        final_query = f"{additional_query} after:{date_str}"
        result["debug_info"]["search_query"] = final_query
        
        # Get all QuickBooks customer domains upfront for comparison
        from beanscounter.services.email_domain_matching_service import get_qb_customer_domains
        try:
            qb_domains = get_qb_customer_domains()
            result["debug_info"]["qb_customer_domains"] = sorted(list(qb_domains))
            if not qb_domains:
                # Check if this is due to authentication failure
                result["errors"].append("Warning: No QuickBooks customer domains found. This may be due to authentication issues. Please check QuickBooks settings.")
        except Exception as e:
            error_msg = str(e)
            if "invalid_grant" in error_msg or "refresh token" in error_msg.lower():
                result["errors"].append("QuickBooks authentication failed: The refresh token is expired or invalid. Please reauthorize QuickBooks in Settings > QuickBooks.")
            else:
                result["errors"].append(f"Failed to fetch QuickBooks customer domains: {error_msg}")
            result["debug_info"]["qb_customer_domains"] = []
        
        # Process each email
        skipped_reasons = {
            "no_email_data": 0,
            "no_sender_email": 0,
            "no_sender_domain": 0,
            "domain_not_in_qb": 0,
            "no_pdf_attachments": 0,
            "po_already_exists": 0
        }
        
        sample_sender_emails = []
        email_domains = {}  # domain -> count
        
        for email_id in email_ids:
            try:
                # Get email details
                email_data = gmail_client.get_email_details(email_id)
                if not email_data:
                    skipped_reasons["no_email_data"] += 1
                    continue
                
                # Get email metadata
                metadata = gmail_client.get_email_metadata(email_data)
                
                # Extract original sender domain
                sender_email = gmail_client.extract_original_sender(email_data)
                if not sender_email:
                    skipped_reasons["no_sender_email"] += 1
                    # Log detailed debug info
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    
                    # Get email body snippet for debugging
                    body_snippet = gmail_client.get_email_body_text(email_data)
                    
                    # Check for forwarded email indicators
                    has_forwarded_indicators = False
                    forwarded_indicators = []
                    if body_snippet:
                        indicators = [
                            "Original Message",
                            "Begin forwarded message",
                            "-----Original Message-----",
                            "On .* wrote:"
                        ]
                        for indicator in indicators:
                            if re.search(indicator, body_snippet, re.IGNORECASE):
                                forwarded_indicators.append(indicator)
                                has_forwarded_indicators = True
                    
                    # Create detailed error message
                    error_message = (
                        f"Could not extract the original sender email address from this forwarded email. "
                        f"The email was forwarded from '{from_header}', but the system could not find the original sender's email address "
                        f"in the email headers (X-Original-From, X-Forwarded-From) or in the email body content. "
                        f"This is needed to match the email against QuickBooks customers. "
                        f"Forwarded email indicators found: {has_forwarded_indicators}."
                    )
                    
                    # Store debug info for this email with error message
                    result["debug_info"]["email_debug"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "from_header": from_header,
                        "has_forwarded_indicators": has_forwarded_indicators,
                        "forwarded_indicators": forwarded_indicators,
                        "error": error_message
                    })
                    continue
                
                sender_domain = extract_domain(sender_email)
                if not sender_domain:
                    skipped_reasons["no_sender_domain"] += 1
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    error_message = (
                        f"Could not extract domain from the original sender email address '{sender_email}'. "
                        f"The email was forwarded from '{from_header}', and while the original sender email was found, "
                        f"the domain portion could not be extracted. This is needed to match against QuickBooks customers."
                    )
                    result["debug_info"]["email_debug"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "from_header": from_header,
                        "has_forwarded_indicators": False,
                        "forwarded_indicators": [],
                        "error": error_message,
                        "sender_email": sender_email
                    })
                    continue
                
                normalized_domain = normalize_domain(sender_domain)
                
                # Collect all domains from emails
                email_domains[normalized_domain] = email_domains.get(normalized_domain, 0) + 1
                
                # Collect sample data for debugging
                if len(sample_sender_emails) < 10:
                    sample_sender_emails.append(sender_email)
                
                # Check if domain matches QuickBooks customer
                if not matches_qb_customer(normalized_domain):
                    skipped_reasons["domain_not_in_qb"] += 1
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    error_message = (
                        f"The original sender's email domain '{normalized_domain}' (from email '{sender_email}') "
                        f"does not match any QuickBooks customer. Only emails from domains that match existing QuickBooks customers are processed."
                    )
                    result["debug_info"]["email_debug"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "from_header": from_header,
                        "has_forwarded_indicators": False,
                        "forwarded_indicators": [],
                        "error": error_message,
                        "sender_email": sender_email,
                        "sender_domain": normalized_domain
                    })
                    continue
                
                # Get customer name from email
                customer_name = get_customer_name_from_email(sender_email)
                if not customer_name:
                    # Fallback to domain-based name
                    from beanscounter.core.domain_utils import domain_to_company_name
                    customer_name = domain_to_company_name(normalized_domain)
                
                # Sanitize customer name for filename
                customer_name_safe = _sanitize_filename(customer_name)
                
                # Extract PO number from email
                po_number = gmail_client.extract_po_number(email_data)
                if not po_number:
                    po_number = "UNKNOWN"
                else:
                    po_number = _sanitize_filename(po_number)
                
                # Check if PO number already exists
                from beanscounter.services.po_metadata_service import po_number_exists, save_po_source
                if po_number_exists(po_number) and po_number != "UNKNOWN":
                    skipped_reasons["po_already_exists"] = skipped_reasons.get("po_already_exists", 0) + 1
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    error_message = (
                        f"PO number '{po_number}' already exists in the system. "
                        f"This email was forwarded from '{from_header}' and will be skipped to avoid duplicates."
                    )
                    result["debug_info"]["email_debug"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "from_header": from_header,
                        "has_forwarded_indicators": False,
                        "forwarded_indicators": [],
                        "error": error_message,
                        "po_number": po_number
                    })
                    continue
                
                # Get PDF attachments
                pdf_attachments = gmail_client.get_pdf_attachments(email_id)
                if not pdf_attachments:
                    skipped_reasons["no_pdf_attachments"] += 1
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    error_message = (
                        f"No PDF attachments found in this email. The email was forwarded from '{from_header}' "
                        f"and the original sender was '{sender_email}', but no PDF files were attached. "
                        f"Only emails with PDF attachments are processed as Purchase Orders."
                    )
                    result["debug_info"]["email_debug"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "from_header": from_header,
                        "has_forwarded_indicators": False,
                        "forwarded_indicators": [],
                        "error": error_message
                    })
                    continue
                
                # Download each PDF attachment
                downloaded_filenames = []
                for attachment in pdf_attachments:
                    try:
                        # Download attachment
                        pdf_data = gmail_client.download_attachment(email_id, attachment["id"])
                        if not pdf_data:
                            result["errors"].append(f"Failed to download attachment {attachment['id']} from email {email_id}")
                            continue
                        
                        # Generate filename: PO_{customer_name}_{po_number}_{MM-DD-YYYY}.pdf
                        date_str = datetime.now().strftime("%m-%d-%Y")
                        filename = f"PO_{customer_name_safe}_{po_number}_{date_str}.pdf"
                        
                        # Ensure unique filename
                        file_path = PO_DIR / filename
                        counter = 1
                        while file_path.exists():
                            base_name = f"PO_{customer_name_safe}_{po_number}_{date_str}"
                            filename = f"{base_name}_{counter}.pdf"
                            file_path = PO_DIR / filename
                            counter += 1
                        
                        # Save PDF file
                        with open(file_path, 'wb') as f:
                            f.write(pdf_data)
                        
                        result["pdfs_downloaded"] += 1
                        result["downloaded_files"].append(filename)
                        downloaded_filenames.append(filename)
                        
                    except Exception as e:
                        error_msg = f"Error downloading attachment {attachment.get('id', 'unknown')}: {str(e)}"
                        result["errors"].append(error_msg)
                        print(error_msg)
                
                # Store successful email info and save source metadata
                if downloaded_filenames:
                    headers = email_data.get("payload", {}).get("headers", [])
                    from_header = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "from"), "Not found")
                    
                    # Save source metadata for this PO
                    # Store both by PO number and by filename (in case PO number extraction differs)
                    # Save for each downloaded filename - this allows lookup by filename even if PO number extraction differs
                    if po_number != "UNKNOWN":
                        for downloaded_filename in downloaded_filenames:
                            save_po_source(
                                po_number=po_number,
                                source_type="email",
                                email_subject=metadata["subject"],
                                email_date=metadata["date"],
                                filename=downloaded_filename  # Store filename so we can look it up later
                            )
                    
                    result["debug_info"]["successful_emails"].append({
                        "email_id": email_id,
                        "subject": metadata["subject"],
                        "date": metadata["date"],
                        "attachment_names": metadata["attachment_names"],
                        "downloaded_filenames": downloaded_filenames,
                        "sender_email": sender_email,
                        "customer_name": customer_name,
                        "po_number": po_number
                    })
                
            except Exception as e:
                error_msg = f"Error processing email {email_id}: {str(e)}"
                result["errors"].append(error_msg)
                print(error_msg)
                continue
        
        # Add summary of skipped emails and debug info
        result["debug_info"]["skipped_reasons"] = skipped_reasons
        result["debug_info"]["sample_sender_emails"] = sample_sender_emails[:10]
        
        # Store all email domains with counts
        result["debug_info"]["email_domains"] = email_domains
        
        # Find matching domains
        matching_domains = []
        for email_domain in email_domains.keys():
            if email_domain in qb_domains:
                matching_domains.append(email_domain)
        result["debug_info"]["matching_domains"] = sorted(matching_domains)
        
        if skipped_reasons:
            summary = "Email filtering summary: "
            summary_parts = [f"{reason}={count}" for reason, count in skipped_reasons.items() if count > 0]
            if summary_parts:
                result["errors"].append(summary + ", ".join(summary_parts))
        
        return result
        
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Sync failed: {str(e)}")
        return result

