"""
PO Metadata Service
Stores and retrieves metadata about POs, including their source (email or file).
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

# Metadata file location
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
METADATA_FILE = BACKEND_ROOT / "data" / "po_metadata.json"


def _ensure_metadata_file():
    """Ensure metadata file exists."""
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        with open(METADATA_FILE, 'w') as f:
            json.dump({}, f, indent=2)


def _load_metadata() -> Dict[str, Any]:
    """Load PO metadata from file."""
    _ensure_metadata_file()
    try:
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_metadata(metadata: Dict[str, Any]):
    """Save PO metadata to file."""
    _ensure_metadata_file()
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def po_number_exists(po_number: str) -> bool:
    """
    Check if a PO number already exists in the system.
    
    Args:
        po_number: PO number to check
        
    Returns:
        True if PO number exists, False otherwise
    """
    metadata = _load_metadata()
    return po_number.lower().strip() in {k.lower().strip() for k in metadata.keys()}


def get_po_source(po_number: str) -> Optional[Dict[str, Any]]:
    """
    Get source information for a PO number.
    
    Args:
        po_number: PO number to look up
        
    Returns:
        Dictionary with source info or None if not found
        Format: {
            "source_type": "email" | "file",
            "email_subject": str (if from email),
            "email_date": str (if from email),
            "filename": str (if from file)
        }
    """
    metadata = _load_metadata()
    # Case-insensitive lookup
    for key, value in metadata.items():
        if key.lower().strip() == po_number.lower().strip():
            return value
    return None


def save_po_source(po_number: str, source_type: str, **kwargs):
    """
    Save source information for a PO number.
    
    Args:
        po_number: PO number
        source_type: "email" or "file"
        **kwargs: Additional source info:
            - For email: email_subject, email_date, filename (optional, to track which file was created)
            - For file: filename
    """
    metadata = _load_metadata()
    
    source_info = {
        "source_type": source_type
    }
    
    if source_type == "email":
        source_info["email_subject"] = kwargs.get("email_subject", "")
        source_info["email_date"] = kwargs.get("email_date", "")
        # Also store filename if provided (for files downloaded from email)
        if "filename" in kwargs:
            source_info["filename"] = kwargs.get("filename", "")
    elif source_type == "file":
        source_info["filename"] = kwargs.get("filename", "")
    
    metadata[po_number] = source_info
    _save_metadata(metadata)


def get_po_source_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    """
    Get source information for a PO by filename.
    This is useful when a file was downloaded from email and we want to find its source.
    
    Args:
        filename: Filename to look up
        
    Returns:
        Dictionary with source info or None if not found
    """
    metadata = _load_metadata()
    # Search through all metadata entries to find one with matching filename
    for key, value in metadata.items():
        if value.get("filename") == filename:
            return value
    return None


def get_all_po_numbers() -> list:
    """
    Get all PO numbers in the system.
    
    Returns:
        List of PO numbers
    """
    metadata = _load_metadata()
    return list(metadata.keys())

