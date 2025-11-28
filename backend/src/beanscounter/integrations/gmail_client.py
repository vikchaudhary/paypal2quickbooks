"""
Gmail Client Module
Provides a client for interacting with the Gmail API.
Handles OAuth2 authentication, email search, and attachment download.
"""

import os
import base64
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """
    Client for interacting with Gmail API.
    
    Handles:
    - OAuth2 authentication and token refresh
    - Email search with date filtering
    - Email details retrieval
    - PDF attachment download
    - Original sender extraction from forwarded emails
    """
    
    def __init__(self, client_id: str, client_secret: str, 
                 access_token: Optional[str] = None, 
                 refresh_token: Optional[str] = None,
                 redirect_uri: Optional[str] = None):
        """
        Initialize Gmail client.
        
        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            access_token: OAuth2 access token (optional)
            refresh_token: OAuth2 refresh token (optional)
            redirect_uri: OAuth2 redirect URI (optional, defaults to env var)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or os.getenv("GMAIL_REDIRECT_URI", "http://localhost:5173/gmail/callback")
        self._service = None
        self._credentials = None
        
        if access_token and refresh_token:
            self._credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
    
    @property
    def service(self):
        """Get Gmail API service, refreshing token if needed."""
        if self._service is None:
            if self._credentials is None:
                raise RuntimeError("Gmail credentials not initialized. Please authenticate first.")
            
            # Refresh token if expired
            if self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
            
            self._service = build('gmail', 'v1', credentials=self._credentials)
        
        return self._service
    
    @staticmethod
    def get_authorization_url(client_id: str, client_secret: str, redirect_uri: str) -> str:
        """
        Generate OAuth2 authorization URL.
        
        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Authorization URL
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url
    
    @staticmethod
    def exchange_code_for_tokens(client_id: str, client_secret: str, 
                                 code: str, redirect_uri: str) -> Dict[str, str]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            code: Authorization code from OAuth callback
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Dictionary with access_token and refresh_token
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token
        }
    
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get Gmail user profile.
        
        Returns:
            User profile dictionary or None if failed
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile
        except HttpError as e:
            print(f"Error getting user profile: {e}")
            return None
    
    def search_emails(self, start_date: datetime, query: str = None) -> List[str]:
        """
        Search for emails matching criteria.
        
        Args:
            start_date: Start date for email search
            query: Additional Gmail search query (optional)
            
        Returns:
            List of email IDs
        """
        try:
            # Build search query
            date_str = start_date.strftime('%Y/%m/%d')
            
            if query:
                # If custom query provided, use it and add date filter
                search_query = f'{query} after:{date_str}'
            else:
                # Default: search for PDF attachments
                search_query = f'has:attachment filename:pdf after:{date_str}'
            
            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=search_query,
                maxResults=500
            ).execute()
            
            messages = results.get('messages', [])
            return [msg['id'] for msg in messages]
        except HttpError as e:
            print(f"Error searching emails: {e}")
            return []
    
    def get_email_details(self, email_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full email details including headers and body.
        
        Args:
            email_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if failed
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            return message
        except HttpError as e:
            print(f"Error getting email details: {e}")
            return None
    
    def get_email_body_text(self, email_data: Dict[str, Any]) -> str:
        """
        Extract plain text body from email data.
        
        Args:
            email_data: Email data from get_email_details()
            
        Returns:
            Plain text body content
        """
        body_text = ""
        payload = email_data.get("payload", {})
        
        def extract_text_from_part(part):
            """Recursively extract text from email parts."""
            text = ""
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            
            # Get text/plain content
            if mime_type == "text/plain":
                data = body.get("data")
                if data:
                    try:
                        text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    except Exception:
                        pass
            
            # Recursively check nested parts
            parts = part.get("parts", [])
            for nested_part in parts:
                text += extract_text_from_part(nested_part)
            
            return text
        
        # Extract from main payload
        body_text = extract_text_from_part(payload)
        
        # Fallback to snippet if no body text found
        if not body_text:
            body_text = email_data.get("snippet", "")
        
        return body_text
    
    def extract_original_sender(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract original sender email from forwarded email.
        
        Args:
            email_data: Email data from get_email_details()
            
        Returns:
            Original sender email address or None
        """
        headers = email_data.get("payload", {}).get("headers", [])
        
        # Build a dict from headers
        header_dict = {}
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            header_dict[name] = value
        
        # Get forwarding email domain to exclude
        forwarding_email = header_dict.get("from", "")
        forwarding_domain = None
        if forwarding_email:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'
            matches = re.findall(email_pattern, forwarding_email)
            if matches:
                forwarding_domain = matches[0].lower()
        
        sender_email = None
        
        # Priority order for headers:
        # 1. X-Original-From
        # 2. X-Forwarded-From
        # 3. From (if not from forwarding domain)
        # 4. Reply-To
        if "x-original-from" in header_dict:
            sender_email = header_dict["x-original-from"]
        elif "x-forwarded-from" in header_dict:
            sender_email = header_dict["x-forwarded-from"]
        elif "from" in header_dict:
            from_header = header_dict["from"]
            # Check if From header is from forwarding domain
            if forwarding_domain and forwarding_domain not in from_header.lower():
                sender_email = from_header
            elif not forwarding_domain and "indianbento.com" not in from_header.lower():
                sender_email = from_header
        elif "reply-to" in header_dict:
            sender_email = header_dict["reply-to"]
        
        # Extract email address from header value
        if sender_email:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            matches = re.findall(email_pattern, sender_email)
            if matches:
                extracted = matches[0]
                # Exclude forwarding domain
                if forwarding_domain and forwarding_domain not in extracted.lower():
                    return extracted
                elif not forwarding_domain and "indianbento.com" not in extracted.lower():
                    return extracted
        
        # Try parsing email body for forwarded email patterns
        body_text = self.get_email_body_text(email_data)
        
        if body_text:
            # Common forwarded email patterns - ordered by specificity and reliability
            # More specific patterns first, then fallback to more general ones
            patterns = [
                # Pattern 1: "---------- Forwarded message ---------\nFrom: Name <email@domain.com>"
                # Example: "---------- Forwarded message ---------\nFrom: Bermet Zumabaeva <bermet.zumabaeva@goodeggs.com>"
                r'-{3,}\s*Forwarded\s+message\s*-{3,}[\s\S]*?From:\s*(?:[^<\n]+<)?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                
                # Pattern 2: "On [date], [name] (email@domain.com) <other@domain.com> wrote:"
                # Example: "On Tue, Nov 18, 2025 at 11:52 AM Chanae Jones (chanae@elevategourmetbrands.com) <system@sent-via.netsuite.com> wrote:"
                # This pattern captures the email in parentheses, which is usually the actual sender
                r'On\s+[^,]+,\s+[^(]+\(([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\)\s*<[^>]+>\s+wrote:',
                
                # Pattern 3: "On [date], [name] <email@domain.com> wrote:"
                # Example: "On Wed, Nov 26, 2025 at 11:26 AM Lee, Denise <Denise.Lee4@ucsf.edu> wrote:"
                r'On\s+[^,]+,\s+[^<]+<([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})>\s+wrote:',
                
                # Pattern 4: "Original Message" or "Begin forwarded message" followed by From:
                r'(?:Original\s+Message|Begin\s+forwarded\s+message)[\s\S]*?From:\s*(?:[^<\n]+<)?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                
                # Pattern 5: "-----Original Message-----" pattern
                r'-{3,}Original\s+Message-{3,}[\s\S]*?From:\s*(?:[^<\n]+<)?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                
                # Pattern 6: "From: email@domain.com" (standalone, at start of line or after whitespace)
                r'(?:^|\n)\s*From:\s*(?:[^<\n]+<)?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                
                # Pattern 7: "On [date], [name] <email@domain.com> wrote:" (simpler, more flexible version)
                r'On\s+.*?<([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})>\s+wrote:',
                
                # Pattern 8: "Sent from" or "Sent by"
                r'Sent\s+(?:from|by):\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
            ]
            
            # Try each pattern in order
            for pattern in patterns:
                matches = re.findall(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if matches:
                    # Check all matches to find one that's not from forwarding domain
                    for extracted in matches:
                        # Exclude forwarding domain
                        if forwarding_domain and forwarding_domain not in extracted.lower():
                            return extracted
                        elif not forwarding_domain and "indianbento.com" not in extracted.lower():
                            return extracted
            
            # Fallback: Look for email addresses in parentheses after names (common in email threads)
            # This is a more general pattern, so we use it as a last resort
            # Example: "Name (email@domain.com)" - but only if it appears early in the body
            # (first 2000 characters to avoid false matches in signatures)
            body_preview = body_text[:2000]
            paren_pattern = r'\(([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\)'
            paren_matches = re.findall(paren_pattern, body_preview, re.IGNORECASE)
            if paren_matches:
                for extracted in paren_matches:
                    # Exclude forwarding domain and common system addresses
                    if forwarding_domain and forwarding_domain not in extracted.lower():
                        # Also exclude common system/notification addresses
                        if not any(sys_domain in extracted.lower() for sys_domain in ['noreply', 'no-reply', 'donotreply', 'system@', 'sent-via']):
                            return extracted
                    elif not forwarding_domain and "indianbento.com" not in extracted.lower():
                        if not any(sys_domain in extracted.lower() for sys_domain in ['noreply', 'no-reply', 'donotreply', 'system@', 'sent-via']):
                            return extracted
        
        # Fallback: try snippet
        snippet = email_data.get("snippet", "")
        if snippet:
            from_pattern = r'From:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            matches = re.findall(from_pattern, snippet, re.IGNORECASE)
            if matches:
                extracted = matches[0]
                # Exclude forwarding domain
                if forwarding_domain and forwarding_domain not in extracted.lower():
                    return extracted
                elif not forwarding_domain and "indianbento.com" not in extracted.lower():
                    return extracted
        
        return None
    
    def get_email_metadata(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from email data (subject, date, attachment names).
        
        Args:
            email_data: Email data from get_email_details()
            
        Returns:
            Dictionary with subject, date, and attachment_names
        """
        headers = email_data.get("payload", {}).get("headers", [])
        header_dict = {}
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            header_dict[name] = value
        
        subject = header_dict.get("subject", "No Subject")
        date_str = header_dict.get("date", "")
        
        # Extract attachment filenames
        attachment_names = []
        payload = email_data.get("payload", {})
        
        def extract_attachments_from_part(part):
            """Recursively extract attachment filenames from email parts."""
            filenames = []
            filename = part.get("filename", "")
            if filename:
                filenames.append(filename)
            
            # Check nested parts
            parts = part.get("parts", [])
            for nested_part in parts:
                filenames.extend(extract_attachments_from_part(nested_part))
            
            return filenames
        
        attachment_names = extract_attachments_from_part(payload)
        
        return {
            "subject": subject,
            "date": date_str,
            "attachment_names": attachment_names
        }
    
    def get_pdf_attachments(self, email_id: str) -> List[Dict[str, Any]]:
        """
        Get all PDF attachments from an email.
        
        Args:
            email_id: Gmail message ID
            
        Returns:
            List of attachment dictionaries with id, filename, size
        """
        try:
            email_data = self.get_email_details(email_id)
            if not email_data:
                return []
            
            attachments = []
            parts = email_data.get("payload", {}).get("parts", [])
            
            def extract_attachments(parts_list):
                for part in parts_list:
                    # Check if this part has attachments
                    if part.get("filename"):
                        mime_type = part.get("mimeType", "")
                        if mime_type == "application/pdf" or part.get("filename", "").lower().endswith(".pdf"):
                            body = part.get("body", {})
                            attachment_id = body.get("attachmentId")
                            if attachment_id:
                                attachments.append({
                                    "id": attachment_id,
                                    "filename": part.get("filename", "attachment.pdf"),
                                    "size": body.get("size", 0),
                                    "mime_type": mime_type
                                })
                    
                    # Recursively check nested parts
                    nested_parts = part.get("parts", [])
                    if nested_parts:
                        extract_attachments(nested_parts)
            
            extract_attachments(parts)
            return attachments
        except HttpError as e:
            print(f"Error getting PDF attachments: {e}")
            return []
    
    def download_attachment(self, email_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download an attachment from an email.
        
        Args:
            email_id: Gmail message ID
            attachment_id: Attachment ID
            
        Returns:
            Attachment data as bytes or None if failed
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=email_id,
                id=attachment_id
            ).execute()
            
            file_data = base64.urlsafe_b64decode(attachment['data'])
            return file_data
        except HttpError as e:
            print(f"Error downloading attachment: {e}")
            return None
    
    def extract_po_number(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PO number from email subject and body.
        
        Args:
            email_data: Email data from get_email_details()
            
        Returns:
            PO number string or None if not found
        """
        # Get subject
        headers = email_data.get("payload", {}).get("headers", [])
        subject = ""
        for header in headers:
            if header.get("name", "").lower() == "subject":
                subject = header.get("value", "")
                break
        
        # Get body snippet
        snippet = email_data.get("snippet", "")
        
        # Search for PO number patterns
        # Common patterns: PO-123, PO #123, Purchase Order 123, P.O. 123
        po_patterns = [
            r'PO[#\s-]?(\d+)',
            r'Purchase\s+Order[#\s-]?(\d+)',
            r'P\.O\.\s*[#\s-]?(\d+)',
            r'PO\s*Number[#\s:]?\s*(\d+)',
            r'PO\s*:\s*(\d+)',
        ]
        
        text_to_search = f"{subject} {snippet}"
        
        for pattern in po_patterns:
            matches = re.findall(pattern, text_to_search, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return None

