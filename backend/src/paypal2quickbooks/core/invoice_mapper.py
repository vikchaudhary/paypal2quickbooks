from typing import Any, Dict

def map_to_quickbooks(parsed: Dict[str, Any]) -> Dict[str, Any]:
    return {"InvoiceNumber": parsed.get("source", "")}
