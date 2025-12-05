from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import subprocess
import platform
from beanscounter.core.po_reader import POReader
from beanscounter.services.invoice_storage_service import get_all_invoice_records
from beanscounter.services.product_mapping_service import (
    get_sku_for_product_string,
    set_product_mapping,
    get_all_mappings,
    get_all_skus,
    bulk_set_mappings,
    clear_all_mappings,
    refresh_skus_from_qb
)
from beanscounter.services.product_matching_service import match_products_to_skus
from beanscounter.services.settings_service import get_qb_credentials
from beanscounter.integrations.quickbooks_client import QuickBooksClient

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

@router.get("/pos/folder-path")
def get_folder_path() -> Dict[str, Any]:
    """Get the current PO folder path."""
    return {"folder_path": str(PO_DIR) if PO_DIR.exists() else None}

@router.get("/pos")
def list_pos() -> List[Dict[str, Any]]:
    """List available PO files with extracted metadata."""
    if not PO_DIR.exists():
        return []
    
    reader = POReader()
    pos = []
    processed_files = []
    
    # Process PDF files
    pdf_files = list(PO_DIR.glob("*.pdf"))
    for f in pdf_files:
        processed_files.append(f.name)
        try:
            # Extract basic metadata from the PO
            extracted = reader.extract_data(f)
            
            # Format amount properly
            invoice_amount = extracted.get("invoice_amount", 0)
            formatted_amount = f"${invoice_amount:.2f}" if invoice_amount else ""
            
            # Get invoice status if invoice exists
            invoice_records = get_all_invoice_records()
            invoice_record = invoice_records.get(f.name)
            
            # Skip files marked as "Not a PO"
            if invoice_record and invoice_record.get("po_status") == "Not a PO":
                continue
            
            status = _determine_po_status(invoice_record)
            
            po_number = extracted.get("po_number", "")
            
            # Get source information if available
            # First check by filename (for files downloaded from email)
            # Then check by PO number (for files uploaded directly)
            from beanscounter.services.po_metadata_service import get_po_source, save_po_source, get_po_source_by_filename
            source_info = get_po_source_by_filename(f.name)
            
            # If not found by filename, try by PO number
            if not source_info and po_number:
                source_info = get_po_source(po_number)
            
            # If no source info exists, this is from a file (uploaded directly, not from email)
            if not source_info and po_number:
                save_po_source(
                    po_number=po_number,
                    source_type="file",
                    filename=f.name
                )
                source_info = get_po_source(po_number)
            
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": extracted.get("customer", "Unknown"),  # Backend uses 'customer'
                "po_number": po_number,
                "date": extracted.get("order_date", ""),  # Backend uses 'order_date'
                "delivery_date": extracted.get("delivery_date", ""),
                "amount": formatted_amount,  # Backend uses 'invoice_amount'
                "status": status,
                "source": source_info
            })
        except Exception as e:
            # If extraction fails, still include the file with minimal info
            print(f"Error extracting {f.name}: {e}")
            # Get invoice status if invoice exists
            invoice_records = get_all_invoice_records()
            invoice_record = invoice_records.get(f.name)
            
            # Skip files marked as "Not a PO"
            if invoice_record and invoice_record.get("po_status") == "Not a PO":
                continue
            
            status = _determine_po_status(invoice_record)
            
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": "Unknown",
                "po_number": "",
                "date": "",
                "delivery_date": "",
                "amount": "",
                "status": status,
                "source": None
            })
    
    # Also process image files
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        image_files = list(PO_DIR.glob(ext))
        for f in image_files:
            processed_files.append(f.name)
            try:
                extracted = reader.extract_data(f)
                
                # Format amount properly
                invoice_amount = extracted.get("invoice_amount", 0)
                formatted_amount = f"${invoice_amount:.2f}" if invoice_amount else ""
                
                # Get invoice status if invoice exists
                invoice_records = get_all_invoice_records()
                invoice_record = invoice_records.get(f.name)
                
                # Skip files marked as "Not a PO"
                if invoice_record and invoice_record.get("po_status") == "Not a PO":
                    continue
                
                status = _determine_po_status(invoice_record)
                
                po_number = extracted.get("po_number", "")
                
                # Get source information if available
                # First check by filename (for files downloaded from email)
                # Then check by PO number (for files uploaded directly)
                from beanscounter.services.po_metadata_service import get_po_source, save_po_source, get_po_source_by_filename
                source_info = get_po_source_by_filename(f.name)
                
                # If not found by filename, try by PO number
                if not source_info and po_number:
                    source_info = get_po_source(po_number)
                
                # If no source info exists, this is from a file (uploaded directly, not from email)
                if not source_info and po_number:
                    save_po_source(
                        po_number=po_number,
                        source_type="file",
                        filename=f.name
                    )
                    source_info = get_po_source(po_number)
                
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": extracted.get("customer", "Unknown"),
                    "po_number": po_number,
                    "date": extracted.get("order_date", ""),
                    "delivery_date": extracted.get("delivery_date", ""),
                    "amount": formatted_amount,
                    "status": status,
                    "source": source_info
                })
            except Exception as e:
                print(f"Error extracting {f.name}: {e}")
                # Get invoice status if invoice exists
                invoice_records = get_all_invoice_records()
                invoice_record = invoice_records.get(f.name)
                
                # Skip files marked as "Not a PO"
                if invoice_record and invoice_record.get("po_status") == "Not a PO":
                    continue
                
                status = _determine_po_status(invoice_record)
                
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": "Unknown",
                    "po_number": "",
                    "date": "",
                    "delivery_date": "",
                    "amount": "",
                    "status": status,
                    "source": None
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
        from beanscounter.services.invoice_storage_service import get_invoice_record, update_invoice_status, mark_as_not_po
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


@router.post("/pos/{po_filename}/mark-not-po")
def mark_po_as_not_po(po_filename: str):
    """
    Mark a PO file as "Not a PO" to hide it from the list.
    
    Args:
        po_filename: PO filename (URL encoded)
        
    Returns:
        Success message
    """
    try:
        from beanscounter.services.invoice_storage_service import mark_as_not_po
        # Decode the filename
        import urllib.parse
        decoded_filename = urllib.parse.unquote(po_filename)
        mark_as_not_po(decoded_filename)
        return {"message": "PO marked as 'Not a PO' and will be hidden from the list"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark PO as not a PO: {str(e)}")


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


@router.get("/products/qb-items")
def get_qb_items() -> Dict[str, Any]:
    """
    Get all QuickBooks items with their SKUs.
    
    Returns:
        {
            "items": [
                {
                    "Id": str,
                    "Name": str,
                    "Sku": str or None,
                    "Type": str
                }
            ]
        }
    """
    try:
        credentials = get_qb_credentials()
        if not credentials:
            raise HTTPException(status_code=400, detail="QuickBooks credentials not configured")
        
        qb_client = QuickBooksClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            realm_id=credentials["realm_id"],
            environment=credentials["environment"]
        )
        
        items = qb_client.get_all_items()
        return {"items": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch QuickBooks items: {str(e)}")


@router.post("/products/match")
def match_products(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Match ProductStrings to QuickBooks SKUs.
    
    Request body:
        {
            "product_strings": ["Product String 1", "Product String 2", ...],
            "threshold": 0.6  # Optional, default 0.6
        }
        
    Returns:
        {
            "matches": {
                "Product String 1": {
                    "sku": str or None,
                    "similarity": float,
                    "matched": bool,
                    "item": dict or None
                },
                ...
            }
        }
    """
    try:
        product_strings = request.get("product_strings", [])
        threshold = request.get("threshold", 0.5)
        
        if not product_strings:
            return {"matches": {}}
        
        # Get QuickBooks items
        credentials = get_qb_credentials()
        if not credentials:
            raise HTTPException(status_code=400, detail="QuickBooks credentials not configured")
        
        qb_client = QuickBooksClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            realm_id=credentials["realm_id"],
            environment=credentials["environment"]
        )
        
        items = qb_client.get_all_items()
        
        # Match products
        matches = match_products_to_skus(product_strings, items, threshold)
        
        return {"matches": matches}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to match products: {str(e)}")


@router.get("/products/mappings")
def get_product_mappings() -> Dict[str, Any]:
    """
    Get all ProductString -> SKU mappings.
    
    Returns:
        {
            "mappings": {
                "ProductString": "SKU",
                ...
            },
            "skus": {
                "SKU": {
                    "name": str or None,
                    "id": str or None,
                    "product_strings": [str, ...]
                },
                ...
            }
        }
    """
    try:
        mappings = get_all_mappings()
        skus = get_all_skus()
        
        # Debug: Log mappings to help diagnose issues
        print(f"DEBUG: Returning {len(mappings)} product mappings")
        if mappings:
            sample_keys = list(mappings.keys())[:5]
            print(f"DEBUG: Sample mapping keys: {sample_keys}")
        
        return {
            "mappings": mappings,
            "skus": skus
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get product mappings: {str(e)}")


@router.post("/products/mappings")
def set_product_mappings(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set ProductString -> SKU mappings.
    
    Request body:
        {
            "mappings": {
                "ProductString": "SKU",
                ...
            },
            "sku_metadata": {  # Optional
                "SKU": {
                    "name": str,
                    "id": str
                },
                ...
            }
        }
        
    Returns:
        {"status": "success"}
    """
    try:
        mappings = request.get("mappings", {})
        sku_metadata = request.get("sku_metadata")
        
        # Allow empty mappings if sku_metadata is provided (for metadata-only updates)
        if not mappings and not sku_metadata:
            raise HTTPException(status_code=400, detail="Either mappings or sku_metadata must be provided")
        
        bulk_set_mappings(mappings, sku_metadata)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set product mappings: {str(e)}")


@router.get("/products/mappings/{product_string}")
def get_product_mapping(product_string: str) -> Dict[str, Any]:
    """
    Get the SKU mapped to a ProductString.
    
    Returns:
        {
            "product_string": str,
            "sku": str or None
        }
    """
    try:
        sku = get_sku_for_product_string(product_string)
        return {
            "product_string": product_string,
            "sku": sku
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get product mapping: {str(e)}")


@router.get("/products/skus")
def get_all_skus_with_mappings() -> Dict[str, Any]:
    """
    Get all SKUs from QuickBooks with their associated ProductStrings.
    This is a 1:many mapping (one SKU maps to many ProductStrings).
    
    Returns:
        {
            "skus": [
                {
                    "sku": str,
                    "name": str,
                    "id": str,
                    "description": str or None,
                    "product_strings": [str, ...]
                },
                ...
            ]
        }
    """
    try:
        # Get all mappings
        mappings = get_all_mappings()
        skus_data = get_all_skus()
        
        # Get all QuickBooks items to get full details
        credentials = get_qb_credentials()
        qb_items = []
        if credentials:
            try:
                qb_client = QuickBooksClient(
                    client_id=credentials["client_id"],
                    client_secret=credentials["client_secret"],
                    refresh_token=credentials["refresh_token"],
                    realm_id=credentials["realm_id"],
                    environment=credentials["environment"]
                )
                qb_items = qb_client.get_all_items()
            except Exception as e:
                print(f"Failed to fetch QB items: {e}")
        
        # Build items_by_identifier lookup (using SKU or Name as identifier)
        # QuickBooks API may return SKU field with different casing
        items_by_identifier = {}
        for item in qb_items:
            # Use SKU as identifier, or fall back to Name if no SKU
            sku = item.get("Sku") or item.get("SKU") or item.get("sku")
            if not sku:
                sku = item.get("Name")
            if sku:
                items_by_identifier[sku] = item
        
        # Build reverse mapping: identifier -> ProductStrings
        identifier_to_product_strings = {}
        for product_string, identifier in mappings.items():
            if identifier not in identifier_to_product_strings:
                identifier_to_product_strings[identifier] = []
            identifier_to_product_strings[identifier].append(product_string)
        
        # Build result list - ALWAYS show ALL items from QuickBooks
        result_skus = []
        processed_identifiers = set()
        
        # First, add ALL items from QuickBooks (using SKU or Name as identifier)
        for item in qb_items:
            # Use SKU as identifier, or fall back to Name if no SKU
            identifier = item.get("Sku") or item.get("SKU") or item.get("sku")
            if not identifier:
                identifier = item.get("Name")
            
            if identifier:
                # Get ProductStrings for this identifier from mappings
                product_strings = identifier_to_product_strings.get(identifier, [])
                
                result_skus.append({
                    "sku": identifier,  # This is the identifier (SKU or Name)
                    "name": item.get("Name") or identifier,
                    "id": item.get("Id"),
                    "description": item.get("Description"),
                    "type": item.get("Type"),
                    "product_strings": sorted(product_strings)
                })
                processed_identifiers.add(identifier)
        
        # Then add any identifiers that have mappings but aren't in QuickBooks anymore
        # (edge case: mapped identifier was deleted from QB)
        for identifier, product_strings in identifier_to_product_strings.items():
            if identifier not in processed_identifiers:
                sku_info = skus_data.get(identifier, {})
                result_skus.append({
                    "sku": identifier,
                    "name": sku_info.get("name") or identifier,
                    "id": sku_info.get("id"),
                    "description": sku_info.get("description"),
                    "type": sku_info.get("type"),
                    "product_strings": sorted(product_strings)
                })
        
        # Sort by Product Name (or SKU if no name)
        result_skus.sort(key=lambda x: (x["name"] or x["sku"]).lower())
        
        return {"skus": result_skus}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SKUs with mappings: {str(e)}")


@router.post("/products/skus/{sku}/product-strings")
def add_product_string_to_sku(sku: str, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a ProductString mapping to a SKU.
    
    Request body:
        {
            "product_string": str
        }
        
    Returns:
        {"status": "success"}
    """
    try:
        product_string = request.get("product_string")
        if not product_string:
            raise HTTPException(status_code=400, detail="product_string is required")
        
        # Get QB item to get name and id
        credentials = get_qb_credentials()
        sku_name = None
        sku_id = None
        
        if credentials:
            try:
                qb_client = QuickBooksClient(
                    client_id=credentials["client_id"],
                    client_secret=credentials["client_secret"],
                    refresh_token=credentials["refresh_token"],
                    realm_id=credentials["realm_id"],
                    environment=credentials["environment"]
                )
                items = qb_client.get_all_items()
                for item in items:
                    if item.get("Sku") == sku:
                        sku_name = item.get("Name")
                        sku_id = item.get("Id")
                        break
            except Exception as e:
                print(f"Failed to fetch QB item: {e}")
        
        set_product_mapping(product_string, sku, sku_name, sku_id)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add product string mapping: {str(e)}")


@router.delete("/products/skus/{sku}/product-strings/{product_string}")
def remove_product_string_from_sku(sku: str, product_string: str) -> Dict[str, Any]:
    """
    Remove a ProductString mapping from a SKU.
    
    Returns:
        {"status": "success"}
    """
    try:
        from beanscounter.services.product_mapping_service import remove_product_mapping
        remove_product_mapping(product_string)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove product string mapping: {str(e)}")


@router.post("/products/refresh")
def refresh_skus() -> Dict[str, Any]:
    """
    Delete all current SKU mappings and reimport SKUs from QuickBooks.
    This will:
    1. Clear all existing mappings
    2. Import all SKUs from QuickBooks
    3. Preserve existing ProductString mappings if the SKU still exists in QuickBooks
    
    Returns:
        {
            "status": "success",
            "skus_imported": int
        }
    """
    try:
        credentials = get_qb_credentials()
        if not credentials:
            raise HTTPException(status_code=400, detail="QuickBooks credentials not configured")
        
        qb_client = QuickBooksClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            realm_id=credentials["realm_id"],
            environment=credentials["environment"]
        )
        
        # Get all items from QuickBooks
        qb_items = qb_client.get_all_items()
        
        # Debug: Log what we're getting from QuickBooks
        print(f"DEBUG: Total items fetched from QuickBooks: {len(qb_items)}")
        if qb_items:
            print(f"DEBUG: Sample item keys: {list(qb_items[0].keys())}")
            print(f"DEBUG: Sample item (first 3): {qb_items[:3]}")
            # Check for SKU in various possible formats across all items
            items_with_sku = [item for item in qb_items if item.get("Sku") or item.get("SKU") or item.get("sku")]
            print(f"DEBUG: Items with SKU: {len(items_with_sku)}")
            if items_with_sku:
                sample_item = items_with_sku[0]
                print(f"DEBUG: Sample item with SKU: {sample_item}")
                print(f"DEBUG: SKU field value: {sample_item.get('Sku') or sample_item.get('SKU') or sample_item.get('sku')}")
            else:
                print(f"DEBUG: No items found with SKU field. Checking first item structure:")
                print(f"DEBUG: First item: {qb_items[0]}")
                # Check all possible SKU field variations
                for key in qb_items[0].keys():
                    if 'sku' in key.lower():
                        print(f"DEBUG: Found potential SKU field: '{key}' = {qb_items[0][key]}")
        
        # Refresh SKUs from QuickBooks
        refresh_skus_from_qb(qb_items)
        
        # Count items imported (using SKU or Name as identifier)
        items_imported = len([
            item for item in qb_items 
            if (item.get("Sku") or item.get("SKU") or item.get("sku")) or item.get("Name")
        ])
        
        print(f"DEBUG: Items imported count: {items_imported}")
        
        return {
            "status": "success",
            "skus_imported": items_imported,
            "total_items": len(qb_items)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh SKUs: {str(e)}")


@router.delete("/products/clear")
def clear_all_product_mappings() -> Dict[str, Any]:
    """
    Clear all product mappings and SKU data.
    This will delete all mappings and SKU information.
    
    Returns:
        {"status": "success"}
    """
    try:
        clear_all_mappings()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear mappings: {str(e)}")
