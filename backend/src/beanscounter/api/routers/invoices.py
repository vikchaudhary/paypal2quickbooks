from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import subprocess
import platform
from beanscounter.core.po_reader import POReader
from beanscounter.services.invoice_storage_service import get_all_invoice_records

# Assuming POs are stored in a 'data/pos' directory relative to backend root
# Adjust this path as needed based on where the user keeps their POs
# backend/src/beanscounter/api/routers/invoices.py -> backend/data/pos
PO_DIR = Path(__file__).parents[5] / "backend" / "data" / "pos" 

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _determine_po_status(invoice_record: Optional[Dict[str, Any]]) -> str:
    """
    Determine PO status based on invoice record.
    
    Status values:
    - "New Order" (default) - No invoice created
    - "Invoice Prepared" - Invoice created in QB but not sent
    - "Invoice Sent" - Invoice has been sent (EmailStatus is not None)
    - "Invoice Paid" - Invoice balance is 0
    
    Args:
        invoice_record: Invoice record from storage or None
        
    Returns:
        Status string
    """
    if not invoice_record:
        return "New Order"
    
    # Check if invoice is paid (balance is 0 or very close to 0)
    balance = invoice_record.get("balance", 0)
    if isinstance(balance, (int, float)) and abs(balance) < 0.01:
        return "Invoice Paid"
    
    # Check if invoice has been sent
    # QuickBooks EmailStatus values: "NotSet", "NeedToSend", "EmailSent"
    # Only "EmailSent" means the invoice was actually sent
    email_status = invoice_record.get("email_status")
    if email_status and email_status.strip() and email_status.strip() == "EmailSent":
        return "Invoice Sent"
    
    # Invoice exists but not sent
    return "Invoice Prepared"

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/pos")
def list_pos() -> List[Dict[str, str]]:
    """List available PO files with extracted metadata."""
    if not PO_DIR.exists():
        return []
    
    reader = POReader()
    pos = []
    
    # Process PDF files
    for f in PO_DIR.glob("*.pdf"):
        try:
            # Extract basic metadata from the PO
            extracted = reader.extract_data(f)
            
            # Format amount properly
            invoice_amount = extracted.get("invoice_amount", 0)
            formatted_amount = f"${invoice_amount:.2f}" if invoice_amount else ""
            
            # Get invoice status if invoice exists
            invoice_records = get_all_invoice_records()
            invoice_record = invoice_records.get(f.name)
            status = _determine_po_status(invoice_record)
            
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": extracted.get("customer", "Unknown"),  # Backend uses 'customer'
                "po_number": extracted.get("po_number", ""),
                "date": extracted.get("order_date", ""),  # Backend uses 'order_date'
                "delivery_date": extracted.get("delivery_date", ""),
                "amount": formatted_amount,  # Backend uses 'invoice_amount'
                "status": status
            })
        except Exception as e:
            # If extraction fails, still include the file with minimal info
            print(f"Error extracting {f.name}: {e}")
            # Get invoice status if invoice exists
            invoice_records = get_all_invoice_records()
            invoice_record = invoice_records.get(f.name)
            status = _determine_po_status(invoice_record)
            
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": "Unknown",
                "po_number": "",
                "date": "",
                "delivery_date": "",
                "amount": "",
                "status": status
            })
    
    # Also process image files
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        for f in PO_DIR.glob(ext):
            try:
                extracted = reader.extract_data(f)
                
                # Format amount properly
                invoice_amount = extracted.get("invoice_amount", 0)
                formatted_amount = f"${invoice_amount:.2f}" if invoice_amount else ""
                
                # Get invoice status if invoice exists
                invoice_records = get_all_invoice_records()
                invoice_record = invoice_records.get(f.name)
                status = _determine_po_status(invoice_record)
                
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": extracted.get("customer", "Unknown"),
                    "po_number": extracted.get("po_number", ""),
                    "date": extracted.get("order_date", ""),
                    "delivery_date": extracted.get("delivery_date", ""),
                    "amount": formatted_amount,
                    "status": status
                })
            except Exception as e:
                print(f"Error extracting {f.name}: {e}")
                # Get invoice status if invoice exists
                invoice_records = get_all_invoice_records()
                invoice_record = invoice_records.get(f.name)
                status = _determine_po_status(invoice_record)
                
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": "Unknown",
                    "po_number": "",
                    "date": "",
                    "delivery_date": "",
                    "amount": "",
                    "status": status
                })
    
    return pos


@router.post("/pos/open-folder")
def open_folder():
    """Open the PO directory in the system file explorer."""
    if not PO_DIR.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    
    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(PO_DIR)])
        elif platform.system() == "Windows":
            os.startfile(str(PO_DIR))
        else:  # Linux
            subprocess.run(["xdg-open", str(PO_DIR)])
        return {"status": "opened"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pos/set-folder")
def set_folder(request: Dict[str, str]):
    """Set the PO directory from frontend folder selection."""
    global PO_DIR
    
    try:
        folder_path = request.get("folder_path")
        if not folder_path:
            raise HTTPException(status_code=400, detail="folder_path is required")
            
        path = Path(folder_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Folder not found")
        if not path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        PO_DIR = path
        return {"status": "success", "path": str(PO_DIR)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@router.get("/pos/{filename}/file")
def get_po_file(filename: str):
    """Serve the raw PO file."""
    file_path = PO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@router.post("/pos/{filename}/parse")
def parse_po(filename: str) -> Dict[str, Any]:
    """Parse the PO file and extract details."""
    file_path = PO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        reader = POReader()
        data = reader.extract_data(file_path)
        
        # Map backend data model to frontend expected format
        # Frontend expects: vendor_name, vendor_address, po_number, date, total_amount, line_items
        # Backend returns: customer, customer_address, po_number, order_date, invoice_amount, items
        
        frontend_items = []
        for item in data.get("items", []):
            try:
                rate = float(item.get('rate', 0))
            except (ValueError, TypeError):
                rate = 0.0
            
            try:
                price = float(item.get('price', 0))
            except (ValueError, TypeError):
                price = 0.0

            frontend_items.append({
                "product_name": item.get("product_name", ""),
                "description": item.get("product_name", ""), # Use product_name as description for now
                "quantity": item.get("quantity", 0),
                "unit_price": f"${rate:.2f}",
                "amount": f"${price:.2f}"
            })
            
        return {
            "vendor_name": data.get("customer", "Unknown"),
            "po_number": data.get("po_number", "Unknown"),
            "date": data.get("order_date", "Unknown"),
            "delivery_date": data.get("delivery_date", "Unknown"),
            "ordered_by": data.get("ordered_by", "Unknown"),
            "customer_email": data.get("customer_email", "Unknown"),
            "total_amount": f"${data.get('invoice_amount', 0):.2f}",
            "bill_to": {
                "name": data.get("customer", "Unknown"),
                "address": data.get("customer_address", "Unknown")
            },
            "ship_to": {
                "name": "Unknown", # Could be extracted if available
                "address": data.get("delivery_address", "Unknown")
            },
            "line_items": frontend_items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/save-to-quickbooks")
def save_invoice_to_quickbooks(request: Dict[str, Any]):
    """
    Save invoice to QuickBooks.
    
    Request body:
        {
            "customer_id": str,
            "po_filename": str,  # PO filename to store the record
            "invoice_data": {
                "customer": str,
                "po_number": str,
                "order_date": str,
                "delivery_date": str,
                "items": [...]
            }
        }
    """
    try:
        customer_id = request.get("customer_id")
        invoice_data = request.get("invoice_data")
        po_filename = request.get("po_filename")
        
        if not customer_id:
            raise HTTPException(status_code=400, detail="customer_id is required")
        if not invoice_data:
            raise HTTPException(status_code=400, detail="invoice_data is required")
        
        from beanscounter.services.po_to_invoice_service import convert_po_to_qb_invoice
        
        result = convert_po_to_qb_invoice(invoice_data, customer_id)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        # Save invoice record if invoice was created successfully and po_filename is provided
        if result["status"] in ("created", "exists") and result.get("invoice") and po_filename:
            from beanscounter.services.invoice_storage_service import save_invoice_record
            from beanscounter.services.settings_service import get_qb_credentials
            from beanscounter.integrations.quickbooks_client import QuickBooksClient
            
            # Fetch full invoice details including status fields
            invoice = result["invoice"]
            invoice_id = invoice.get("Id")
            if invoice_id:
                # Get full invoice details with status
                try:
                    credentials = get_qb_credentials()
                    if credentials:
                        qb_client = QuickBooksClient(
                            client_id=credentials["client_id"],
                            client_secret=credentials["client_secret"],
                            refresh_token=credentials["refresh_token"],
                            realm_id=credentials["realm_id"],
                            environment=credentials["environment"]
                        )
                        status_info = qb_client.get_invoice_status(invoice_id)
                        if status_info:
                            # Merge status info into invoice data
                            invoice["EmailStatus"] = status_info.get("email_status")
                            invoice["Balance"] = status_info.get("balance")
                            invoice["TotalAmt"] = status_info.get("total_amount")
                except Exception as e:
                    print(f"Failed to get invoice status: {e}")
            save_invoice_record(po_filename, invoice)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save invoice: {str(e)}")


@router.get("/invoice-record/{po_filename}")
def get_invoice_record(po_filename: str):
    """
    Get invoice record for a PO file.
    
    Args:
        po_filename: PO filename (e.g., "PO123.pdf")
        
    Returns:
        Invoice record with status or null if not found
    """
    try:
        from beanscounter.services.invoice_storage_service import get_invoice_record, update_invoice_status
        from beanscounter.services.settings_service import get_qb_credentials
        from beanscounter.integrations.quickbooks_client import QuickBooksClient
        
        record = get_invoice_record(po_filename)
        if record and record.get("qb_invoice_id"):
            # Refresh status from QuickBooks
            try:
                credentials = get_qb_credentials()
                if credentials:
                    qb_client = QuickBooksClient(
                        client_id=credentials["client_id"],
                        client_secret=credentials["client_secret"],
                        refresh_token=credentials["refresh_token"],
                        realm_id=credentials["realm_id"],
                        environment=credentials["environment"]
                    )
                    status_info = qb_client.get_invoice_status(record["qb_invoice_id"])
                    if status_info:
                        update_invoice_status(
                            po_filename,
                            email_status=status_info.get("email_status"),
                            balance=status_info.get("balance")
                        )
                        # Reload record with updated status
                        record = get_invoice_record(po_filename)
            except Exception as e:
                print(f"Failed to refresh invoice status: {e}")
        
        # Add computed status to record
        if record:
            record["status"] = _determine_po_status(record)
        
        return {"invoice_record": record} if record else {"invoice_record": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get invoice record: {str(e)}")


@router.post("/suggest-company-from-email")
def suggest_company_from_email(request: Dict[str, Any]):
    """
    Suggest company name from email address.
    
    Request body:
        {
            "email": "user@acme.com"
        }
        
    Returns:
        {
            "suggested_name": "Acme",
            "source": "quickbooks" | "heuristic"
        }
    """
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="email is required")
        
        from beanscounter.services.domain_matching_service import get_company_name_from_email, extract_domain, match_domain_to_company
        from beanscounter.core.domain_utils import normalize_domain
        
        # Try QuickBooks search first
        source = "heuristic"
        suggested_name = None
        
        try:
            from beanscounter.services.settings_service import get_qb_credentials
            from beanscounter.integrations.quickbooks_client import QuickBooksClient
            credentials = get_qb_credentials()
            if credentials:
                qb_client = QuickBooksClient(
                    client_id=credentials["client_id"],
                    client_secret=credentials["client_secret"],
                    refresh_token=credentials["refresh_token"],
                    realm_id=credentials["realm_id"],
                    environment=credentials["environment"]
                )
                
                # Extract domain and search
                domain = extract_domain(email)
                if domain:
                    from beanscounter.services.qb_customer_service import search_customers_by_domain
                    customers = search_customers_by_domain(domain)
                    if customers:
                        # Use first match
                        suggested_name = customers[0].get("company_name") or customers[0].get("display_name") or customers[0].get("name")
                        source = "quickbooks"
        except Exception as e:
            # QB not configured or search failed, continue to heuristic
            print(f"QuickBooks search failed: {e}")
        
        # Fallback to heuristic if no QB match
        if not suggested_name:
            suggested_name = get_company_name_from_email(email, None)
            source = "heuristic"
        
        return {
            "suggested_name": suggested_name,
            "source": source
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to suggest company name: {str(e)}")
