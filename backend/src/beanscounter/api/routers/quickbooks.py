"""
QuickBooks API Router
Handles QuickBooks customer search and retrieval, and invoice number generation.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from beanscounter.services.qb_customer_service import search_customers, get_customer
from beanscounter.services.settings_service import get_qb_credentials, get_max_invoice_number_attempts
from beanscounter.integrations.quickbooks_client import QuickBooksClient

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])


def _get_qb_client() -> QuickBooksClient:
    """Get QuickBooks client instance using stored credentials."""
    credentials = get_qb_credentials()
    if not credentials:
        raise RuntimeError("QuickBooks credentials not configured")
    
    return QuickBooksClient(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        refresh_token=credentials["refresh_token"],
        realm_id=credentials["realm_id"],
        environment=credentials["environment"]
    )


@router.get("/customers/search")
def search_qb_customers(q: str = Query(..., description="Search term for customer name")):
    """
    Search QuickBooks customers by name.
    
    Args:
        q: Search term
        
    Returns:
        List of matching customers
    """
    try:
        customers = search_customers(q)
        return {"customers": customers}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search customers: {str(e)}")


@router.get("/customers/{customer_id}")
def get_qb_customer(customer_id: str):
    """
    Get specific QuickBooks customer by ID.
    
    Args:
        customer_id: QuickBooks customer ID
        
    Returns:
        Customer details
    """
    try:
        customer = get_customer(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get customer: {str(e)}")


@router.get("/invoices/last-for-customer/{customer_id}")
def get_last_invoice_for_customer(customer_id: str):
    """
    Get the most recent invoice for a customer.
    
    Args:
        customer_id: QuickBooks customer ID
        
    Returns:
        Last invoice data or null if no invoices exist
    """
    try:
        qb_client = _get_qb_client()
        invoice = qb_client.find_last_invoice_for_customer(customer_id)
        return {"invoice": invoice} if invoice else {"invoice": None}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get last invoice: {str(e)}")


@router.get("/invoices/check-number")
def check_invoice_number(docnumber: str = Query(..., description="Invoice document number to check")):
    """
    Check if an invoice with the given document number already exists.
    
    Args:
        docnumber: Invoice document number
        
    Returns:
        Object with exists boolean
    """
    try:
        qb_client = _get_qb_client()
        exists = qb_client.invoice_number_exists(docnumber)
        return {"exists": exists}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check invoice number: {str(e)}")


@router.get("/invoices/next-number/{customer_id}")
def get_next_invoice_number(customer_id: str):
    """
    Get the next available invoice number for a customer.
    Finds the last invoice, increments the number, and verifies it doesn't exist
    in the entire QuickBooks account (not just for this customer).
    
    Args:
        customer_id: QuickBooks customer ID
        
    Returns:
        Next available invoice number
    """
    try:
        qb_client = _get_qb_client()
        
        # Find last invoice for customer
        last_invoice = qb_client.find_last_invoice_for_customer(customer_id)
        
        if not last_invoice or not last_invoice.get("DocNumber"):
            # No previous invoices, start with 1
            next_number = "1"
        else:
            # Extract number from last invoice DocNumber
            last_doc_number = last_invoice.get("DocNumber", "")
            
            # Try to extract numeric part and increment
            import re
            # Find the last sequence of digits in the doc number
            numbers = re.findall(r'\d+', last_doc_number)
            if numbers:
                # Get the last number found (in case there are multiple)
                last_num = int(numbers[-1])
                next_num = last_num + 1
                
                # Replace the last number with incremented value
                # Find the position of the last number
                last_match = None
                for match in re.finditer(r'\d+', last_doc_number):
                    last_match = match
                
                if last_match:
                    # Replace the last number with incremented value
                    next_number = (
                        last_doc_number[:last_match.start()] + 
                        str(next_num) + 
                        last_doc_number[last_match.end():]
                    )
                else:
                    next_number = str(next_num)
            else:
                # No numbers found, append "1"
                next_number = last_doc_number + "1"
        
        # ALWAYS verify the number doesn't already exist in the entire QuickBooks account
        # Keep incrementing until we find an unused invoice number
        max_attempts = get_max_invoice_number_attempts()
        attempt = 0
        while qb_client.invoice_number_exists(next_number) and attempt < max_attempts:
            # If it exists, increment and try again
            import re
            numbers = re.findall(r'\d+', next_number)
            if numbers:
                last_num = int(numbers[-1])
                next_num = last_num + 1
                last_match = None
                for match in re.finditer(r'\d+', next_number):
                    last_match = match
                if last_match:
                    next_number = (
                        next_number[:last_match.start()] + 
                        str(next_num) + 
                        next_number[last_match.end():]
                    )
                else:
                    next_number = str(next_num)
            else:
                next_number = str(int(next_number) + 1) if next_number.isdigit() else next_number + "1"
            attempt += 1
        
        if attempt >= max_attempts:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to find available invoice number after {max_attempts} attempts"
            )
        
        return {"invoice_number": next_number}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get next invoice number: {str(e)}")

