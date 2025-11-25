from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any
import os
import subprocess
import platform
from beanscounter.core.po_reader import POReader

# Assuming POs are stored in a 'data/pos' directory relative to backend root
# Adjust this path as needed based on where the user keeps their POs
# backend/src/beanscounter/api/routers/invoices.py -> backend/data/pos
PO_DIR = Path(__file__).parents[5] / "backend" / "data" / "pos" 

router = APIRouter(prefix="/invoices", tags=["invoices"])

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
            
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": extracted.get("customer", "Unknown"),  # Backend uses 'customer'
                "po_number": extracted.get("po_number", ""),
                "date": extracted.get("order_date", ""),  # Backend uses 'order_date'
                "delivery_date": extracted.get("delivery_date", ""),
                "amount": formatted_amount,  # Backend uses 'invoice_amount'
                "status": "Open"  # Default status
            })
        except Exception as e:
            # If extraction fails, still include the file with minimal info
            print(f"Error extracting {f.name}: {e}")
            pos.append({
                "id": f.name,
                "filename": f.name,
                "vendor_name": "Unknown",
                "po_number": "",
                "date": "",
                "delivery_date": "",
                "amount": "",
                "status": "Open"
            })
    
    # Also process image files
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        for f in PO_DIR.glob(ext):
            try:
                extracted = reader.extract_data(f)
                
                # Format amount properly
                invoice_amount = extracted.get("invoice_amount", 0)
                formatted_amount = f"${invoice_amount:.2f}" if invoice_amount else ""
                
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": extracted.get("customer", "Unknown"),
                    "po_number": extracted.get("po_number", ""),
                    "date": extracted.get("order_date", ""),
                    "delivery_date": extracted.get("delivery_date", ""),
                    "amount": formatted_amount,
                    "status": "Open"
                })
            except Exception as e:
                print(f"Error extracting {f.name}: {e}")
                pos.append({
                    "id": f.name,
                    "filename": f.name,
                    "vendor_name": "Unknown",
                    "po_number": "",
                    "date": "",
                    "delivery_date": "",
                    "amount": "",
                    "status": "Open"
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
