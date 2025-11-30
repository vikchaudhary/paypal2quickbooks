"""
Product Mapping Service
Stores and retrieves mappings between ProductString (from PO Line Items) and SKU (from QuickBooks).
This is a many:1 mapping - multiple ProductStrings can map to the same SKU.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

# Get backend root directory
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
STORAGE_FILE = BACKEND_ROOT / "data" / "product_mappings.json"


def _ensure_data_dir():
    """Ensure the data directory exists."""
    STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_mappings() -> Dict[str, Any]:
    """Load product mappings from storage file."""
    _ensure_data_dir()
    if not STORAGE_FILE.exists():
        return {
            "mappings": {},  # product_string -> sku
            "skus": {}  # sku -> {name, id, product_strings: []}
        }
    
    try:
        with open(STORAGE_FILE, 'r') as f:
            data = json.load(f)
            # Ensure backward compatibility
            if "mappings" not in data:
                # Old format: just a dict of product_string -> sku
                old_mappings = data if isinstance(data, dict) else {}
                data = {
                    "mappings": old_mappings,
                    "skus": {}
                }
                # Rebuild skus dict from mappings
                for product_string, sku in old_mappings.items():
                    if sku not in data["skus"]:
                        data["skus"][sku] = {
                            "product_strings": []
                        }
                    if product_string not in data["skus"][sku]["product_strings"]:
                        data["skus"][sku]["product_strings"].append(product_string)
            return data
    except Exception as e:
        print(f"Error loading product mappings: {e}")
        return {
            "mappings": {},
            "skus": {}
        }


def _save_mappings(data: Dict[str, Any]):
    """Save product mappings to storage file."""
    _ensure_data_dir()
    try:
        with open(STORAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving product mappings: {e}")
        raise


def get_sku_for_product_string(product_string: str) -> Optional[str]:
    """
    Get the SKU mapped to a ProductString.
    Performs case-insensitive and whitespace-normalized lookup.
    
    Args:
        product_string: ProductString from PO Line Item
        
    Returns:
        SKU string or None if not mapped
    """
    if not product_string:
        return None
    
    # Special debug logging for specific ProductString from good-eggs-po-PO_GE351293.pdf
    TARGET_PRODUCT_STRING = "Chana Masala Roti Paratha (8 oz)"
    is_target = product_string == TARGET_PRODUCT_STRING or product_string.strip() == TARGET_PRODUCT_STRING
    
    if is_target:
        print("=" * 80)
        print(f"🔍 DEBUG [good-eggs-po-PO_GE351293.pdf] Starting lookup for ProductString: '{product_string}'")
        print("=" * 80)
    
    data = _load_mappings()
    mappings = data.get("mappings", {})
    
    if is_target:
        print(f"📊 Total mappings in Products database: {len(mappings)}")
        if len(mappings) > 0:
            print(f"📋 Sample mapping keys (first 10): {list(mappings.keys())[:10]}")
    
    # Try exact match first
    if product_string in mappings:
        result = mappings[product_string]
        if is_target:
            print(f"✅ MATCH FOUND (Test 1: Exact match)")
            print(f"   Operator: Direct dictionary lookup with key='{product_string}'")
            print(f"   Result: ProductString -> SKU='{result}'")
            print("=" * 80)
        return result
    
    # Try normalized match (trimmed)
    normalized_key = product_string.strip()
    if is_target:
        print(f"❌ Test 1 FAILED: No exact match found")
        print(f"   Trying Test 2: Trimmed whitespace match")
        print(f"   Normalized key: '{normalized_key}'")
    
    if normalized_key in mappings:
        result = mappings[normalized_key]
        if is_target:
            print(f"✅ MATCH FOUND (Test 2: Trimmed whitespace match)")
            print(f"   Operator: Dictionary lookup with normalized key='{normalized_key}'")
            print(f"   Result: ProductString -> SKU='{result}'")
            print("=" * 80)
        return result
    
    # Try case-insensitive match
    normalized_lower = normalized_key.lower()
    if is_target:
        print(f"❌ Test 2 FAILED: No trimmed match found")
        print(f"   Trying Test 3: Case-insensitive match")
        print(f"   Normalized lowercase key: '{normalized_lower}'")
        print(f"   Searching through {len(mappings)} mapping keys...")
    
    for key, value in mappings.items():
        key_normalized = key.strip().lower()
        if is_target and key_normalized == normalized_lower:
            print(f"✅ MATCH FOUND (Test 3: Case-insensitive match)")
            print(f"   Operator: Iteration with case-insensitive comparison")
            print(f"   Found key in DB: '{key}' (normalized: '{key_normalized}')")
            print(f"   Result: ProductString -> SKU='{value}'")
            print("=" * 80)
            return value
    
    if is_target:
        print(f"❌ Test 3 FAILED: No case-insensitive match found")
        print(f"❌ NO MATCH FOUND in Products database for '{product_string}'")
        print(f"   Tests performed:")
        print(f"   1. Exact match: product_string in mappings")
        print(f"   2. Trimmed match: product_string.strip() in mappings")
        print(f"   3. Case-insensitive match: key.strip().lower() == product_string.strip().lower()")
        print("=" * 80)
    
    return None


def get_product_strings_for_sku(sku: str) -> List[str]:
    """
    Get all ProductStrings mapped to a SKU.
    
    Args:
        sku: SKU from QuickBooks
        
    Returns:
        List of ProductStrings mapped to this SKU
    """
    data = _load_mappings()
    sku_info = data["skus"].get(sku, {})
    return sku_info.get("product_strings", [])


def set_product_mapping(product_string: str, sku: str, sku_name: Optional[str] = None, sku_id: Optional[str] = None):
    """
    Set a mapping from ProductString to SKU.
    This is a many:1 mapping - multiple ProductStrings can map to the same SKU.
    Normalizes the product_string key to avoid duplicates from whitespace differences.
    
    Args:
        product_string: ProductString from PO Line Item
        sku: SKU from QuickBooks
        sku_name: Optional SKU name for reference
        sku_id: Optional SKU ID for reference
    """
    if not product_string or not sku:
        return
    
    data = _load_mappings()
    
    # Normalize the product_string key (trim whitespace)
    normalized_key = product_string.strip()
    
    # Check if there's an existing mapping with a different key (whitespace variant)
    # Remove old mappings with different whitespace
    keys_to_remove = []
    for key in data["mappings"].keys():
        if key.strip() == normalized_key and key != normalized_key:
            keys_to_remove.append(key)
            old_sku = data["mappings"][key]
            # Remove from old SKU's product_strings list
            if old_sku in data["skus"]:
                if key in data["skus"][old_sku].get("product_strings", []):
                    data["skus"][old_sku]["product_strings"].remove(key)
    
    for key in keys_to_remove:
        del data["mappings"][key]
    
    # Remove old mapping if product_string was mapped to a different SKU
    old_sku = data["mappings"].get(normalized_key)
    if old_sku and old_sku != sku:
        # Remove from old SKU's product_strings list
        if old_sku in data["skus"]:
            if normalized_key in data["skus"][old_sku].get("product_strings", []):
                data["skus"][old_sku]["product_strings"].remove(normalized_key)
    
    # Set new mapping with normalized key
    data["mappings"][normalized_key] = sku
    
    # Update SKU info
    if sku not in data["skus"]:
        data["skus"][sku] = {
            "product_strings": [],
            "name": sku_name,
            "id": sku_id
        }
    
    # Add normalized product_string to SKU's list if not already there
    if normalized_key not in data["skus"][sku]["product_strings"]:
        data["skus"][sku]["product_strings"].append(normalized_key)
    
    # Update SKU metadata if provided
    if sku_name:
        data["skus"][sku]["name"] = sku_name
    if sku_id:
        data["skus"][sku]["id"] = sku_id
    
    _save_mappings(data)


def remove_product_mapping(product_string: str):
    """
    Remove a mapping for a ProductString.
    
    Args:
        product_string: ProductString to remove mapping for
    """
    data = _load_mappings()
    
    if product_string in data["mappings"]:
        sku = data["mappings"][product_string]
        del data["mappings"][product_string]
        
        # Remove from SKU's product_strings list
        if sku in data["skus"]:
            if product_string in data["skus"][sku].get("product_strings", []):
                data["skus"][sku]["product_strings"].remove(product_string)
        
        _save_mappings(data)


def get_all_mappings() -> Dict[str, str]:
    """
    Get all ProductString -> SKU mappings.
    
    Returns:
        Dictionary mapping ProductString to SKU
    """
    data = _load_mappings()
    return data.get("mappings", {}).copy()


def get_all_skus() -> Dict[str, Any]:
    """
    Get all SKUs with their metadata.
    
    Returns:
        Dictionary mapping SKU to metadata (name, id, product_strings)
    """
    data = _load_mappings()
    return data.get("skus", {}).copy()


def bulk_set_mappings(mappings: Dict[str, str], sku_metadata: Optional[Dict[str, Dict[str, Any]]] = None):
    """
    Set multiple mappings at once.
    
    Args:
        mappings: Dictionary of product_string -> sku
        sku_metadata: Optional dictionary of sku -> {name, id}
    """
    data = _load_mappings()
    
    # Update mappings
    for product_string, sku in mappings.items():
        # Remove old mapping if exists
        old_sku = data["mappings"].get(product_string)
        if old_sku and old_sku != sku:
            if old_sku in data["skus"]:
                if product_string in data["skus"][old_sku].get("product_strings", []):
                    data["skus"][old_sku]["product_strings"].remove(product_string)
        
        # Set new mapping
        data["mappings"][product_string] = sku
        
        # Update SKU info
        if sku not in data["skus"]:
            data["skus"][sku] = {
                "product_strings": [],
                "name": None,
                "id": None,
                "description": None
            }
        
        if product_string not in data["skus"][sku]["product_strings"]:
            data["skus"][sku]["product_strings"].append(product_string)
    
    # Update SKU metadata if provided
    if sku_metadata:
        for sku, metadata in sku_metadata.items():
            # Ensure SKU entry exists before updating metadata
            if sku not in data["skus"]:
                data["skus"][sku] = {
                    "product_strings": [],
                    "name": None,
                    "id": None,
                    "description": None
                }
            
            # Update metadata fields if provided and not None
            if "name" in metadata and metadata["name"] is not None:
                data["skus"][sku]["name"] = metadata["name"]
            if "id" in metadata and metadata["id"] is not None:
                data["skus"][sku]["id"] = metadata["id"]
            if "description" in metadata and metadata["description"] is not None:
                data["skus"][sku]["description"] = metadata["description"]
    
    _save_mappings(data)


def clear_all_mappings() -> None:
    """
    Clear all product mappings and SKU data.
    This will delete all mappings and SKU information.
    """
    data = {
        "mappings": {},
        "skus": {}
    }
    _save_mappings(data)


def refresh_skus_from_qb(qb_items: List[Dict[str, Any]]) -> None:
    """
    Refresh SKU list from QuickBooks items.
    This will:
    1. Clear all existing mappings
    2. Import all items from QuickBooks (using SKU as key, or Name if no SKU)
    3. Preserve existing ProductString mappings if the SKU/Name still exists
    
    Args:
        qb_items: List of QuickBooks items with Id, Name, Sku, Description, Type
    """
    # Get current mappings to preserve them
    current_data = _load_mappings()
    current_mappings = current_data.get("mappings", {}).copy()
    
    # Build new SKU data from QuickBooks
    new_skus = {}
    new_mappings = {}
    
    # Import all items from QuickBooks
    # Use SKU as the key, or fall back to Name if no SKU
    for item in qb_items:
        # Try multiple possible field names for SKU
        sku = item.get("Sku") or item.get("SKU") or item.get("sku")
        
        # If no SKU, use Name as the identifier
        if not sku:
            sku = item.get("Name")
        
        if sku:  # Process items with SKU or Name
            new_skus[sku] = {
                "product_strings": [],
                "name": item.get("Name"),
                "id": item.get("Id"),
                "description": item.get("Description"),
                "type": item.get("Type")
            }
            
            # Preserve existing ProductString mappings if SKU/Name still exists
            for product_string, mapped_sku in current_mappings.items():
                if mapped_sku == sku:
                    new_mappings[product_string] = sku
                    new_skus[sku]["product_strings"].append(product_string)
    
    # Save new data
    data = {
        "mappings": new_mappings,
        "skus": new_skus
    }
    _save_mappings(data)

