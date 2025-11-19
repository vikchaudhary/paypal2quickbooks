"""
CSV Reader Module

Provides functionality for parsing CSV files containing invoice data.
"""

import csv
from datetime import datetime, timedelta
from typing import Dict, Any, List


def _parse_date_auto(s: str) -> datetime:
    """
    Parse a date string in various common formats.
    
    Args:
        s: Date string to parse
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If date format is unrecognized
    """
    if not s:
        return None
    s = s.strip()
    # Try common formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date format: {s}")


def parse_csv(path: str) -> Dict[str, Any]:
    """
    Parse a CSV file containing invoice data.
    
    Args:
        path: Path to the CSV file
        
    Returns:
        Dictionary with parsed invoice data:
        {
            "customer": str,
            "invoice_number": str,
            "invoice_date": str (YYYY-MM-DD),
            "due_date": str (YYYY-MM-DD),
            "terms": str,
            "lines": List[Dict] - line items with name, description, qty, rate, taxable
        }
        
    Raises:
        ValueError: If CSV is missing required columns or has invalid data
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for raw in rdr:
            row = {(k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                  for k, v in raw.items()}
            rows.append(row)
    if not rows:
        raise ValueError("CSV had no data rows.")

    def g(row, *names, default=""):
        """Helper to get case-insensitive column value"""
        for n in names:
            for k in row.keys():
                if k and k.lower() == n.lower():
                    return row[k]
        return default

    # Validate required columns
    required = ["Customer", "InvoiceNumber", "Item", "Qty", "Rate"]
    missing = [r for r in required if all((h or "").lower() != r.lower() for h in rows[0].keys())]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    # Ensure one invoice number
    inv_numbers = {g(r, "InvoiceNumber") for r in rows}
    if len(inv_numbers) != 1:
        raise ValueError(f"CSV contains multiple InvoiceNumbers: {inv_numbers}")
    invoice_number = inv_numbers.pop()

    customer = g(rows[0], "Customer")
    invoice_date_str = g(rows[0], "InvoiceDate")
    due_date_str = g(rows[0], "DueDate")
    terms = g(rows[0], "Terms")  # e.g., "Net 15"

    # Compute dates
    invoice_dt = _parse_date_auto(invoice_date_str) if invoice_date_str else datetime.utcnow()
    due_dt = _parse_date_auto(due_date_str) if due_date_str else None
    if (not due_dt) and terms and terms.lower().strip().startswith("net"):
        try:
            net_days = int(terms.split()[-1])
            due_dt = invoice_dt + timedelta(days=net_days)
        except Exception:
            pass

    line_items = []
    for r in rows:
        item_name = g(r, "Item")
        desc = g(r, "Description")
        qty = g(r, "Qty") or "1"
        rate = g(r, "Rate") or "0"
        taxable_raw = g(r, "Taxable")
        taxable = str(taxable_raw).lower() in ("y", "yes", "true", "1") if taxable_raw != "" else False

        try:
            qty_f = float(qty)
            rate_f = float(rate)
        except Exception:
            raise ValueError(f"Bad Qty/Rate in row: {r}")

        line_items.append({
            "name": item_name,
            "description": desc,
            "qty": qty_f,
            "rate": rate_f,
            "taxable": taxable,
        })

    payload = {
        "customer": customer,
        "invoice_number": invoice_number,
        "invoice_date": invoice_dt.strftime("%Y-%m-%d"),
        "due_date": due_dt.strftime("%Y-%m-%d") if due_dt else "",
        "terms": terms,
        "lines": line_items,
    }
    return payload