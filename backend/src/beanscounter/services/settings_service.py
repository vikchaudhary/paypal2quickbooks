"""
Settings service for managing QuickBooks credentials.
Stores encrypted credentials in a JSON file.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from beanscounter.core.encryption import encrypt_value, decrypt_value, get_encryption_key


# Get backend root directory (backend/src/beanscounter/services/settings_service.py -> backend/)
# Path: services -> beanscounter -> src -> backend
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


def save_qb_credentials(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    realm_id: str,
    environment: str = "production"
) -> None:
    """
    Save QuickBooks credentials (encrypted).
    
    Args:
        client_id: QuickBooks OAuth2 client ID
        client_secret: QuickBooks OAuth2 client secret
        refresh_token: OAuth2 refresh token
        realm_id: QuickBooks company ID
        environment: "production" or "sandbox"
    """
    key = get_encryption_key()
    
    settings = _load_settings()
    settings["quickbooks"] = {
        "client_id": encrypt_value(client_id, key),
        "client_secret": encrypt_value(client_secret, key),
        "refresh_token": encrypt_value(refresh_token, key),
        "realm_id": encrypt_value(realm_id, key),
        "environment": environment  # Not sensitive, store as-is
    }
    _save_settings(settings)


def get_qb_credentials() -> Optional[Dict[str, str]]:
    """
    Retrieve and decrypt QuickBooks credentials.
    
    Returns:
        Dictionary with credentials or None if not configured
        Keys: client_id, client_secret, refresh_token, realm_id, environment
    """
    settings = _load_settings()
    qb_settings = settings.get("quickbooks")
    
    if not qb_settings:
        return None
    
    try:
        key = get_encryption_key()
        return {
            "client_id": decrypt_value(qb_settings["client_id"], key),
            "client_secret": decrypt_value(qb_settings["client_secret"], key),
            "refresh_token": decrypt_value(qb_settings["refresh_token"], key),
            "realm_id": decrypt_value(qb_settings["realm_id"], key),
            "environment": qb_settings.get("environment", "production")
        }
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt QuickBooks credentials: {e}")


def has_qb_credentials() -> bool:
    """
    Check if QuickBooks credentials are configured.
    
    Returns:
        True if credentials exist, False otherwise
    """
    settings = _load_settings()
    return "quickbooks" in settings and settings["quickbooks"]


def delete_qb_credentials() -> None:
    """Remove QuickBooks configuration."""
    settings = _load_settings()
    if "quickbooks" in settings:
        del settings["quickbooks"]
        _save_settings(settings)


def test_qb_connection() -> Dict[str, Any]:
    """
    Test QuickBooks API connection with stored credentials.
    
    Returns:
        Dictionary with test result: {"success": bool, "message": str}
    """
    try:
        credentials = get_qb_credentials()
        if not credentials:
            return {"success": False, "message": "QuickBooks credentials not configured"}
        
        from beanscounter.integrations.quickbooks_client import QuickBooksClient
        
        client = QuickBooksClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            realm_id=credentials["realm_id"],
            environment=credentials["environment"]
        )
        
        # Try to get access token (this will test the connection)
        token = client.access_token
        if token:
            return {"success": True, "message": "Connection successful"}
        else:
            return {"success": False, "message": "Failed to obtain access token"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


def get_max_invoice_number_attempts() -> int:
    """
    Get the maximum number of attempts for finding an available invoice number.
    
    Returns:
        Maximum attempts (default: 100)
    """
    settings = _load_settings()
    return settings.get("max_invoice_number_attempts", 100)


def save_max_invoice_number_attempts(max_attempts: int) -> None:
    """
    Save the maximum number of attempts for finding an available invoice number.
    
    Args:
        max_attempts: Maximum number of attempts (must be > 0)
    """
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than 0")
    
    settings = _load_settings()
    settings["max_invoice_number_attempts"] = max_attempts
    _save_settings(settings)

