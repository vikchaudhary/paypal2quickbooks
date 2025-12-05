"""
Invoice Storage Service
Stores invoice creation records to persist across sessions.
Maps PO files to QuickBooks invoices.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Get backend root directory (backend/src/beanscounter/services/invoice_storage_service.py -> backend/)
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
STORAGE_FILE = BACKEND_ROOT / "data" / "invoices.json"


def _ensure_data_dir():
    """Ensure the data directory exists."""
    STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_invoices() -> Dict[str, Any]:
    """Load invoice records from storage file."""
    _ensure_data_dir()
    if not STORAGE_FILE.exists():
        return {}
    
    try:
        with open(STORAGE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading invoices: {e}")
        return {}


def _save_invoices(invoices: Dict[str, Any]):
    """Save invoice records to storage file."""
    _ensure_data_dir()
    try:
        with open(STORAGE_FILE, 'w') as f:
            json.dump(invoices, f, indent=2)
    except Exception as e:
        print(f"Error saving invoices: {e}")
        raise


def save_invoice_record(po_filename: str, invoice_data: Dict[str, Any]) -> None:
    """
    Save an invoice record for a PO file.
    
    Args:
        po_filename: PO filename (e.g., "PO123.pdf")
        invoice_data: Invoice data from QuickBooks including:
            - Id: QuickBooks invoice ID
            - DocNumber: Invoice document number
            - TxnDate: Transaction date
            - CustomerRef: Customer reference object
    """
    invoices = _load_invoices()
    
    # Extract customer info safely
    customer_ref = invoice_data.get("CustomerRef")
    customer_id = None
    customer_name = None
    if isinstance(customer_ref, dict):
        customer_id = customer_ref.get("value")
        customer_name = customer_ref.get("name")
    
    # Extract invoice status info
    email_status = invoice_data.get("EmailStatus")
    balance = float(invoice_data.get("Balance", 0)) if invoice_data.get("Balance") else 0
    total_amount = float(invoice_data.get("TotalAmt", 0)) if invoice_data.get("TotalAmt") else 0
    
    invoices[po_filename] = {
        "qb_invoice_id": invoice_data.get("Id"),
        "doc_number": invoice_data.get("DocNumber"),
        "txn_date": invoice_data.get("TxnDate"),
        "created_at": datetime.now().isoformat(),
        "customer_id": customer_id,
        "customer_name": customer_name,
        "email_status": email_status,
        "balance": balance,
        "total_amount": total_amount,
        "last_status_check": datetime.now().isoformat()
    }
    
    _save_invoices(invoices)


def get_invoice_record(po_filename: str) -> Optional[Dict[str, Any]]:
    """
    Get invoice record for a PO file.
    
    Args:
        po_filename: PO filename (e.g., "PO123.pdf")
        
    Returns:
        Invoice record or None if not found
    """
    invoices = _load_invoices()
    return invoices.get(po_filename)


def get_all_invoice_records() -> Dict[str, Any]:
    """
    Get all invoice records.
    
    Returns:
        Dictionary mapping PO filenames to invoice records
    """
    return _load_invoices()


def update_invoice_status(po_filename: str, email_status: Optional[str] = None, balance: Optional[float] = None) -> None:
    """
    Update invoice status information.
    
    Args:
        po_filename: PO filename
        email_status: Email status from QuickBooks
        balance: Current balance from QuickBooks
    """
    invoices = _load_invoices()
    if po_filename in invoices:
        if email_status is not None:
            invoices[po_filename]["email_status"] = email_status
        if balance is not None:
            invoices[po_filename]["balance"] = balance
        invoices[po_filename]["last_status_check"] = datetime.now().isoformat()
        _save_invoices(invoices)


def mark_as_not_po(po_filename: str) -> None:
    """
    Mark a PO file as "Not a PO" to hide it from the list.
    
    Args:
        po_filename: PO filename (e.g., "PO123.pdf")
    """
    invoices = _load_invoices()
    
    # Create or update record with "Not a PO" status
    if po_filename not in invoices:
        invoices[po_filename] = {}
    
    invoices[po_filename]["po_status"] = "Not a PO"
    invoices[po_filename]["marked_at"] = datetime.now().isoformat()
    
    _save_invoices(invoices)

