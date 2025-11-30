"""
PO to Invoice Converter Service
Converts PO data structure to QuickBooks invoice format and creates invoice.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from beanscounter.services.settings_service import get_qb_credentials
from beanscounter.integrations.quickbooks_client import QuickBooksClient
from beanscounter.services.product_mapping_service import get_sku_for_product_string


def _format_date_for_qb(date_str: str) -> str:
    """
    Convert date string to QuickBooks format (YYYY-MM-DD).
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    if not date_str or date_str == "Unknown":
        return None
    
    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If no format matches, try to parse as-is
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _map_po_items_to_qb_lines(po_items: List[Dict[str, Any]], qb_client: QuickBooksClient) -> List[Dict[str, Any]]:
    """
    Convert PO line items to QuickBooks line items.
    Uses product mapping to match ProductString to SKU when available.
    Only uses existing QuickBooks items - does NOT create new items.
    Unmatched products are added as DescriptionOnly lines (no item reference).
    
    Args:
        po_items: List of PO items with product_name, quantity, rate, price
        qb_client: QuickBooksClient instance
        
    Returns:
        List of QuickBooks line item objects
    """
    line_objects = []
    
    # Get all QuickBooks items to look up by SKU (read-only)
    all_items = qb_client.get_all_items()
    items_by_sku = {}
    for qb_item in all_items:
        sku = qb_item.get("Sku")
        if sku:
            items_by_sku[sku] = qb_item
    
    for item in po_items:
        product_name = item.get("product_name", "")
        if not product_name:
            continue
        
        qty = float(item.get("quantity", 0))
        rate = float(item.get("rate", 0))
        price = float(item.get("price", 0))
        
        # Calculate amount if not provided
        if price == 0 and qty > 0 and rate > 0:
            price = qty * rate
        
        # Try to find mapped SKU
        sku = get_sku_for_product_string(product_name)
        
        if sku and sku in items_by_sku:
            # Use the item with the matched SKU (existing item only)
            qb_item = items_by_sku[sku]
            item_ref = {"value": qb_item["Id"], "name": qb_item.get("Name", product_name)}
        
            # Build SalesItemLineDetail with item reference
        detail = {
            "DetailType": "SalesItemLineDetail",
            "Amount": round(price, 2),
            "Description": product_name,
            "SalesItemLineDetail": {
                "ItemRef": item_ref,
                "Qty": qty,
                "UnitPrice": rate,
                "TaxCodeRef": {"value": "NON"}  # Default to non-taxable
            }
        }
        else:
            # No match found - use DescriptionOnly line (no item reference)
            # This allows the product to appear on the invoice without creating a new item
            detail = {
                "DetailType": "DescriptionOnly",
                "Amount": round(price, 2),
                "Description": f"{product_name} (Qty: {qty}, Rate: ${rate:.2f})"
            }
        
        line_objects.append(detail)
    
    return line_objects


def convert_po_to_qb_invoice(po_details: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
    """
    Convert PO data to QuickBooks invoice and create it.
    
    Args:
        po_details: PO data dictionary with customer, po_number, order_date, items, etc.
        customer_id: QuickBooks customer ID (must be valid)
        
    Returns:
        Dictionary with status and invoice data:
        {
            "status": "created"|"exists"|"error",
            "invoice": {...} or None,
            "error": str or None
        }
        
    Raises:
        RuntimeError: If credentials not configured or API fails
        ValueError: If customer_id is invalid
    """
    # Get credentials
    credentials = get_qb_credentials()
    if not credentials:
        raise RuntimeError("QuickBooks credentials not configured")
    
    # Initialize QuickBooks client
    qb_client = QuickBooksClient(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        refresh_token=credentials["refresh_token"],
        realm_id=credentials["realm_id"],
        environment=credentials["environment"]
    )
    
    # Get customer reference
    try:
        # Verify customer exists
        customer_query = f"select Id, DisplayName from Customer where Id = '{customer_id}'"
        customer_res = qb_client.query(customer_query)
        customers = customer_res.get("QueryResponse", {}).get("Customer", [])
        
        if not customers:
            raise ValueError(f"Customer with ID {customer_id} not found in QuickBooks")
        
        customer = customers[0]
        customer_ref = {"value": customer["Id"], "name": customer.get("DisplayName", "")}
    except Exception as e:
        raise ValueError(f"Invalid customer ID: {e}")
    
    # Get invoice number from PO (use invoice_number if provided, otherwise po_number)
    doc_number = po_details.get("invoice_number") or po_details.get("po_number", "Unknown")
    if doc_number == "Unknown":
        # Generate from source file if available
        source_file = po_details.get("source_file", "")
        if source_file:
            doc_number = source_file.replace(".pdf", "").replace(".png", "").replace(".jpg", "")
        else:
            doc_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Check if invoice already exists
    existing = qb_client.find_invoice_by_docnumber(doc_number)
    if existing:
        return {
            "status": "exists",
            "invoice": existing,
            "error": None
        }
    
    # Format dates
    invoice_date = _format_date_for_qb(po_details.get("order_date"))
    if not invoice_date:
        invoice_date = datetime.now().strftime("%Y-%m-%d")
    
    due_date = _format_date_for_qb(po_details.get("delivery_date"))
    
    # Convert line items
    po_items = po_details.get("items", [])
    line_objects = _map_po_items_to_qb_lines(po_items, qb_client)
    
    if not line_objects:
        raise ValueError("No valid line items found in PO data")
    
    # Build invoice body
    invoice_body = qb_client.build_invoice_body(
        customer_ref=customer_ref,
        doc_number=doc_number,
        invoice_date=invoice_date,
        due_date=due_date,
        term_ref=None,  # No terms from PO
        line_objects=line_objects
    )
    
    # Create invoice
    try:
        created = qb_client.create_invoice(invoice_body)
        return {
            "status": "created",
            "invoice": created,
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "invoice": None,
            "error": str(e)
        }

