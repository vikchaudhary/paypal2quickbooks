"""
Settings API Router
Handles QuickBooks settings management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from beanscounter.services.settings_service import (
    save_qb_credentials,
    get_qb_credentials,
    has_qb_credentials,
    delete_qb_credentials,
    test_qb_connection,
    get_max_invoice_number_attempts,
    save_max_invoice_number_attempts
)

router = APIRouter(prefix="/settings", tags=["settings"])


class QBSettingsRequest(BaseModel):
    client_id: str
    client_secret: str
    refresh_token: str
    realm_id: str
    environment: str = "production"


class QBSettingsResponse(BaseModel):
    configured: bool
    environment: Optional[str] = None
    client_id_masked: Optional[str] = None
    realm_id: Optional[str] = None


def _mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret value, showing only last N characters."""
    if not value or len(value) <= show_chars:
        return "*" * len(value) if value else ""
    return "*" * (len(value) - show_chars) + value[-show_chars:]


@router.get("/quickbooks", response_model=QBSettingsResponse)
def get_qb_settings():
    """Get QuickBooks settings (with masked secrets)."""
    if not has_qb_credentials():
        return QBSettingsResponse(configured=False)
    
    try:
        creds = get_qb_credentials()
        return QBSettingsResponse(
            configured=True,
            environment=creds.get("environment"),
            client_id_masked=_mask_secret(creds.get("client_id", "")),
            realm_id=creds.get("realm_id")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve settings: {str(e)}")


@router.post("/quickbooks")
def save_qb_settings(settings: QBSettingsRequest):
    """Create or update QuickBooks settings."""
    try:
        save_qb_credentials(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            refresh_token=settings.refresh_token,
            realm_id=settings.realm_id,
            environment=settings.environment
        )
        return {"message": "QuickBooks settings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.delete("/quickbooks")
def delete_qb_settings():
    """Delete QuickBooks settings."""
    try:
        delete_qb_credentials()
        return {"message": "QuickBooks settings deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete settings: {str(e)}")


@router.post("/quickbooks/test")
def test_qb_settings():
    """Test QuickBooks connection with stored credentials."""
    result = test_qb_connection()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/invoice-number-attempts")
def get_invoice_number_attempts():
    """Get the maximum number of attempts for finding an available invoice number."""
    try:
        max_attempts = get_max_invoice_number_attempts()
        return {"max_attempts": max_attempts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get setting: {str(e)}")


@router.post("/invoice-number-attempts")
def save_invoice_number_attempts(request: Dict[str, int]):
    """Set the maximum number of attempts for finding an available invoice number."""
    try:
        max_attempts = request.get("max_attempts")
        if max_attempts is None:
            raise HTTPException(status_code=400, detail="max_attempts is required")
        if not isinstance(max_attempts, int) or max_attempts <= 0:
            raise HTTPException(status_code=400, detail="max_attempts must be a positive integer")
        
        save_max_invoice_number_attempts(max_attempts)
        return {"message": "Setting saved successfully", "max_attempts": max_attempts}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save setting: {str(e)}")

