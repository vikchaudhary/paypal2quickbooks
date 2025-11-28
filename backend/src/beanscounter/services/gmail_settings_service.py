"""
Gmail Settings Service
Manages Gmail OAuth2 credentials and sync settings.
Stores encrypted credentials in a JSON file.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from beanscounter.core.encryption import encrypt_value, decrypt_value, get_encryption_key


# Get backend root directory (backend/src/beanscounter/services/gmail_settings_service.py -> backend/)
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
SETTINGS_FILE = BACKEND_ROOT / "data" / "settings.json"


def _ensure_data_dir():
    """Ensure the data directory exists."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_settings() -> Dict[str, Any]:
    """Load settings from file."""
    _ensure_data_dir()
    if not SETTINGS_FILE.exists():
        return {}
    
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(settings: Dict[str, Any]):
    """Save settings to file."""
    _ensure_data_dir()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def save_gmail_oauth_credentials(client_id: str, client_secret: str, redirect_uri: str) -> None:
    """
    Save Gmail OAuth2 client credentials (encrypted).
    
    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        redirect_uri: OAuth2 redirect URI
    """
    key = get_encryption_key()
    
    settings = _load_settings()
    if "gmail" not in settings:
        settings["gmail"] = {}
    
    settings["gmail"]["client_id"] = encrypt_value(client_id, key)
    settings["gmail"]["client_secret"] = encrypt_value(client_secret, key)
    settings["gmail"]["redirect_uri"] = redirect_uri  # Not sensitive, store as-is
    
    _save_settings(settings)


def save_gmail_tokens(access_token: str, refresh_token: str) -> None:
    """
    Save Gmail OAuth2 tokens (encrypted).
    
    Args:
        access_token: OAuth2 access token
        refresh_token: OAuth2 refresh token
    """
    key = get_encryption_key()
    
    settings = _load_settings()
    if "gmail" not in settings:
        settings["gmail"] = {}
    
    settings["gmail"]["access_token"] = encrypt_value(access_token, key)
    settings["gmail"]["refresh_token"] = encrypt_value(refresh_token, key)
    
    _save_settings(settings)


def get_gmail_oauth_credentials() -> Optional[Dict[str, str]]:
    """
    Retrieve and decrypt Gmail OAuth2 client credentials.
    
    Returns:
        Dictionary with credentials or None if not configured
        Keys: client_id, client_secret, redirect_uri
    """
    settings = _load_settings()
    gmail_settings = settings.get("gmail")
    
    if not gmail_settings:
        return None
    
    if "client_id" not in gmail_settings or "client_secret" not in gmail_settings:
        return None
    
    try:
        key = get_encryption_key()
        return {
            "client_id": decrypt_value(gmail_settings["client_id"], key),
            "client_secret": decrypt_value(gmail_settings["client_secret"], key),
            "redirect_uri": gmail_settings.get("redirect_uri", "http://localhost:5173/gmail/callback")
        }
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt Gmail OAuth credentials: {e}")


def get_gmail_tokens() -> Optional[Dict[str, str]]:
    """
    Retrieve and decrypt Gmail OAuth2 tokens.
    
    Returns:
        Dictionary with tokens or None if not configured
        Keys: access_token, refresh_token
    """
    settings = _load_settings()
    gmail_settings = settings.get("gmail")
    
    if not gmail_settings:
        return None
    
    if "access_token" not in gmail_settings or "refresh_token" not in gmail_settings:
        return None
    
    try:
        key = get_encryption_key()
        return {
            "access_token": decrypt_value(gmail_settings["access_token"], key),
            "refresh_token": decrypt_value(gmail_settings["refresh_token"], key)
        }
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt Gmail tokens: {e}")


def get_gmail_credentials() -> Optional[Dict[str, str]]:
    """
    Retrieve all Gmail credentials (OAuth + tokens).
    
    Returns:
        Dictionary with all credentials or None if not configured
        Keys: client_id, client_secret, redirect_uri, access_token, refresh_token
    """
    oauth_creds = get_gmail_oauth_credentials()
    tokens = get_gmail_tokens()
    
    if not oauth_creds:
        return None
    
    result = oauth_creds.copy()
    if tokens:
        result.update(tokens)
    
    return result


def has_gmail_credentials() -> bool:
    """
    Check if Gmail credentials are configured.
    
    Returns:
        True if OAuth credentials and tokens exist, False otherwise
    """
    settings = _load_settings()
    gmail_settings = settings.get("gmail")
    if not gmail_settings:
        return False
    
    # Check for OAuth credentials (client_id, client_secret)
    has_oauth = "client_id" in gmail_settings and "client_secret" in gmail_settings
    # Check for tokens (access_token, refresh_token)
    has_tokens = "access_token" in gmail_settings and "refresh_token" in gmail_settings
    
    return has_oauth and has_tokens


def delete_gmail_credentials() -> None:
    """Remove Gmail configuration."""
    settings = _load_settings()
    if "gmail" in settings:
        del settings["gmail"]
        _save_settings(settings)


def save_gmail_starting_date(date: str) -> None:
    """
    Save Gmail sync starting date.
    
    Args:
        date: Starting date in ISO format (YYYY-MM-DD)
    """
    settings = _load_settings()
    if "gmail" not in settings:
        settings["gmail"] = {}
    
    settings["gmail"]["starting_date"] = date
    _save_settings(settings)


def get_gmail_starting_date() -> Optional[str]:
    """
    Get Gmail sync starting date.
    
    Returns:
        Starting date in ISO format (YYYY-MM-DD) or None if not set
    """
    settings = _load_settings()
    gmail_settings = settings.get("gmail")
    if not gmail_settings:
        return None
    
    return gmail_settings.get("starting_date")


def save_gmail_forwarding_email(email: str) -> None:
    """
    Save Gmail forwarding email address.
    
    Args:
        email: Email address that forwards POs (e.g., "pashmina@indianbento.com")
    """
    settings = _load_settings()
    if "gmail" not in settings:
        settings["gmail"] = {}
    
    settings["gmail"]["forwarding_email"] = email
    _save_settings(settings)


def get_gmail_forwarding_email() -> Optional[str]:
    """
    Get Gmail forwarding email address.
    
    Returns:
        Forwarding email address or None if not set
    """
    settings = _load_settings()
    gmail_settings = settings.get("gmail")
    if not gmail_settings:
        return None
    
    return gmail_settings.get("forwarding_email")


def test_gmail_connection() -> Dict[str, Any]:
    """
    Test Gmail API connection with stored credentials.
    
    Returns:
        Dictionary with test result: {"success": bool, "message": str}
    """
    try:
        credentials = get_gmail_credentials()
        if not credentials:
            return {"success": False, "message": "Gmail credentials not configured"}
        
        if "client_id" not in credentials or "client_secret" not in credentials:
            return {"success": False, "message": "Gmail OAuth2 credentials (client_id, client_secret) not configured"}
        
        if "access_token" not in credentials or "refresh_token" not in credentials:
            return {"success": False, "message": "Gmail tokens not configured. Please connect your Gmail account first."}
        
        from beanscounter.integrations.gmail_client import GmailClient
        
        client = GmailClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            access_token=credentials["access_token"],
            refresh_token=credentials["refresh_token"],
            redirect_uri=credentials.get("redirect_uri", "http://localhost:5173/gmail/callback")
        )
        
        # Try to get user profile (this will test the connection)
        profile = client.get_user_profile()
        if profile:
            return {"success": True, "message": f"Connection successful. Email: {profile.get('emailAddress', 'Unknown')}"}
        else:
            return {"success": False, "message": "Failed to get user profile"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}

