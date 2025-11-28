"""
Gmail API Router
Handles Gmail OAuth2 authentication and email syncing.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from beanscounter.services.gmail_settings_service import (
    save_gmail_oauth_credentials,
    save_gmail_tokens,
    get_gmail_oauth_credentials,
    get_gmail_tokens,
    get_gmail_credentials,
    has_gmail_credentials,
    delete_gmail_credentials,
    save_gmail_starting_date,
    get_gmail_starting_date,
    save_gmail_forwarding_email,
    get_gmail_forwarding_email,
    test_gmail_connection
)
from beanscounter.integrations.gmail_client import GmailClient
from beanscounter.services.gmail_sync_service import sync_emails_from_gmail


router = APIRouter(prefix="/gmail", tags=["gmail"])


# Sync history file
BACKEND_ROOT = Path(__file__).parents[5] / "backend"
SYNC_HISTORY_FILE = BACKEND_ROOT / "data" / "gmail_sync_history.json"


def _load_sync_history() -> Dict[str, Any]:
    """Load sync history from file."""
    if not SYNC_HISTORY_FILE.exists():
        return {}
    
    try:
        with open(SYNC_HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_sync_history(history: Dict[str, Any]):
    """Save sync history to file."""
    SYNC_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


class GmailSettingsRequest(BaseModel):
    starting_date: Optional[str] = None  # ISO format YYYY-MM-DD
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    forwarding_email: Optional[str] = None  # Email address that forwards POs


class GmailOAuthCallbackRequest(BaseModel):
    code: str


class GmailSettingsResponse(BaseModel):
    configured: bool
    starting_date: Optional[str] = None
    client_id_masked: Optional[str] = None
    redirect_uri: Optional[str] = None
    forwarding_email: Optional[str] = None
    tokens_configured: Optional[bool] = None  # Whether access/refresh tokens are configured


def _mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret value, showing only last N characters."""
    if not value or len(value) <= show_chars:
        return "*" * len(value) if value else ""
    return "*" * (len(value) - show_chars) + value[-show_chars:]


@router.get("/authorize")
def get_authorization_url():
    """
    Get OAuth2 authorization URL for Gmail.
    
    Returns:
        Authorization URL
    """
    oauth_creds = get_gmail_oauth_credentials()
    
    if not oauth_creds:
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth2 credentials (client_id, client_secret) not configured. Please configure them in Settings."
        )
    
    try:
        auth_url = GmailClient.get_authorization_url(
            oauth_creds["client_id"],
            oauth_creds["client_secret"],
            oauth_creds["redirect_uri"]
        )
        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate authorization URL: {str(e)}")


@router.post("/oauth/callback")
def oauth_callback(request: GmailOAuthCallbackRequest):
    """
    Handle OAuth2 callback and exchange code for tokens.
    
    Args:
        request: OAuth callback request with authorization code
        
    Returns:
        Success message
    """
    oauth_creds = get_gmail_oauth_credentials()
    
    if not oauth_creds:
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth2 credentials (client_id, client_secret) not configured. Please configure them in Settings."
        )
    
    try:
        tokens = GmailClient.exchange_code_for_tokens(
            client_id=oauth_creds["client_id"],
            client_secret=oauth_creds["client_secret"],
            code=request.code,
            redirect_uri=oauth_creds["redirect_uri"]
        )
        
        # Save tokens (OAuth credentials should already be saved)
        save_gmail_tokens(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"]
        )
        
        return {"message": "Gmail connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange code for tokens: {str(e)}")


@router.get("/settings", response_model=GmailSettingsResponse)
def get_gmail_settings():
    """Get Gmail settings (configured status, starting date, masked credentials)."""
    oauth_creds = get_gmail_oauth_credentials()
    tokens = get_gmail_tokens()
    
    if not oauth_creds:
        return GmailSettingsResponse(configured=False)
    
    starting_date = get_gmail_starting_date()
    forwarding_email = get_gmail_forwarding_email()
    
    return GmailSettingsResponse(
        configured=True,
        starting_date=starting_date,
        client_id_masked=_mask_secret(oauth_creds["client_id"]) if oauth_creds else None,
        redirect_uri=oauth_creds["redirect_uri"] if oauth_creds else None,
        forwarding_email=forwarding_email,
        tokens_configured=tokens is not None
    )


@router.post("/settings")
def save_gmail_settings(settings: GmailSettingsRequest):
    """Save Gmail settings (starting date, OAuth credentials, forwarding email)."""
    try:
        # Save starting date if provided
        if settings.starting_date:
            # Validate date format
            datetime.fromisoformat(settings.starting_date)
            save_gmail_starting_date(settings.starting_date)
        
        # Save forwarding email if provided
        if settings.forwarding_email:
            save_gmail_forwarding_email(settings.forwarding_email)
        
        # Save OAuth credentials if provided
        if settings.client_id and settings.client_secret:
            redirect_uri = settings.redirect_uri or "http://localhost:5173/gmail/callback"
            save_gmail_oauth_credentials(
                client_id=settings.client_id,
                client_secret=settings.client_secret,
                redirect_uri=redirect_uri
            )
        
        return {"message": "Gmail settings saved successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.delete("/settings")
def delete_gmail_settings():
    """Delete Gmail configuration."""
    try:
        delete_gmail_credentials()
        return {"message": "Gmail settings deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete settings: {str(e)}")


@router.post("/test")
def test_gmail_settings():
    """Test Gmail connection with stored credentials."""
    result = test_gmail_connection()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/sync")
def sync_gmail_emails(start_date: Optional[str] = None):
    """
    Manual sync trigger - fetch emails and download PDFs.
    
    Args:
        start_date: Optional start date in ISO format (YYYY-MM-DD)
        
    Returns:
        Sync results
    """
    try:
        # Parse start date if provided
        parsed_start_date = None
        if start_date:
            try:
                parsed_start_date = datetime.fromisoformat(start_date)
            except ValueError:
                # Try YYYY-MM-DD format
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        # Run sync
        sync_result = sync_emails_from_gmail(parsed_start_date)
        
        # Save sync history
        history = {
            "last_sync": datetime.now().isoformat(),
            "emails_processed": sync_result["emails_processed"],
            "pdfs_downloaded": sync_result["pdfs_downloaded"],
            "errors": sync_result["errors"],
            "downloaded_files": sync_result.get("downloaded_files", [])
        }
        _save_sync_history(history)
        
        return sync_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/sync/status")
def get_sync_status():
    """Get last sync status/results."""
    history = _load_sync_history()
    if not history:
        return {"message": "No sync history available"}
    return history

