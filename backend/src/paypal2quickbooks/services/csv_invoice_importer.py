#!/usr/bin/env python3
"""
CSV Invoice Importer

Creates QuickBooks Online Invoices from CSV files.
This module orchestrates the process of:
1. Reading CSV invoice data
2. Authenticating with QuickBooks Online
3. Creating or finding necessary entities (customers, items)
4. Creating invoices

CSV required columns (case-insensitive; extra columns ignored):
  Customer, InvoiceNumber, InvoiceDate, DueDate, Terms, Item, Description, Qty, Rate, Taxable
Each row = one line item for the SAME invoice number.

Usage:
  export QBO_CLIENT_ID=...
  export QBO_CLIENT_SECRET=...
  export QBO_REFRESH_TOKEN=...
  export QBO_REALM_ID=...
  python -m paypal2quickbooks.services.csv_invoice_importer path/to/invoice.csv
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any, List

# Import refactored modules
from paypal2quickbooks.core.csv_reader import parse_csv
from paypal2quickbooks.integrations.quickbooks_client import QuickBooksClient


def create_invoice_from_csv(csv_path: str) -> Dict[str, Any]:
    """
    Create a QuickBooks invoice from CSV data.
    
    Args:
        csv_path: Path to the CSV file
        
    Returns:
        Dict with status and invoice data
        
    Raises:
        RuntimeError: If API requests fail
        ValueError: If CSV data is invalid
    """
    # Create QuickBooks client from environment variables
    qb_client = QuickBooksClient.from_env()
    
    # Parse CSV data
    payload = parse_csv(csv_path)
    
    # Idempotency: if DocNumber already exists, exit gracefully
    existing = qb_client.find_invoice_by_docnumber(payload["invoice_number"])
    if existing:
        return {"status": "exists", "invoice": existing}

    # Ensure customer
    cust_ref = qb_client.ensure_customer(payload["customer"])

    # Optional: ensure terms by name if present
    term_ref = qb_client.ensure_sales_term_ref(payload["terms"]) if payload["terms"] else None

    # Build line objects (ensuring Items exist)
    line_objects = []
    for ln in payload["lines"]:
        item_ref = qb_client.ensure_item(ln["name"], taxable=ln["taxable"])
        amount = round(ln["qty"] * ln["rate"], 2)
        detail = {
            "DetailType": "SalesItemLineDetail",
            "Amount": amount,
            "Description": ln["description"] or ln["name"],
            "SalesItemLineDetail": {
                "ItemRef": item_ref,
                "Qty": ln["qty"],
                "UnitPrice": ln["rate"],
                "TaxCodeRef": {"value": "TAX"} if ln["taxable"] else {"value": "NON"}
            }
        }
        line_objects.append(detail)

    # Build invoice body
    inv_body = qb_client.build_invoice_body(
        customer_ref=cust_ref,
        doc_number=payload["invoice_number"],
        invoice_date=payload["invoice_date"],
        due_date=payload["due_date"],
        term_ref=term_ref,
        line_objects=line_objects
    )

    # Create invoice
    created = qb_client.create_invoice(inv_body)
    return {"status": "created", "invoice": created}


def main():
    """Command-line entry point for CSV invoice import."""
    if len(sys.argv) != 2:
        print("Usage: python -m paypal2quickbooks.services.csv_invoice_importer path/to/invoice.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    try:
        result = create_invoice_from_csv(csv_path)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
