"""
Product Matching Service
Matches ProductString (from PO Line Items) to SKU (from QuickBooks).

Matching priority:
1. First check Products database for existing ProductString -> SKU mapping
2. If found, verify SKU exists in QuickBooks and return match
3. If not found, use fuzzy word-based matching (50% word match threshold)
"""

from typing import Dict, Any, Optional, List, Tuple, Set
import re
from beanscounter.services.product_mapping_service import get_sku_for_product_string, get_all_skus


def _normalize_word(word: str) -> str:
    """
    Normalize a single word for comparison.
    
    Args:
        word: Word to normalize
        
    Returns:
        Normalized word (lowercase, special chars removed, "&" -> "and")
    """
    if not word:
        return ""
    # Convert to lowercase
    word = word.lower().strip()
    # Replace "&" with "and"
    word = word.replace("&", "and")
    # Remove punctuation (keep alphanumeric)
    word = re.sub(r'[^a-z0-9]', '', word)
    return word


def _extract_words(text: str) -> List[str]:
    """
    Extract and normalize words from a string.
    Handles parentheses, punctuation, and special characters like "&".
    
    Args:
        text: String to extract words from
        
    Returns:
        List of normalized words (duplicates preserved for now, will be deduplicated in sets)
    """
    if not text:
        return []
    
    # Split by whitespace and punctuation boundaries
    # \b\w+\b matches word boundaries - captures words and numbers
    # This handles "8 oz" as separate tokens "8" and "oz"
    words = re.findall(r'\b\w+\b', text)
    
    # Normalize each word (handles "&" -> "and", lowercase, removes punctuation)
    normalized = [_normalize_word(w) for w in words if w]
    
    # Remove empty strings
    return [w for w in normalized if w]


def _calculate_word_match_percentage(str1: str, str2: str) -> float:
    """
    Calculate the percentage of words from str1 that match words in str2.
    A word matches if it appears in both strings (after normalization).
    
    Args:
        str1: First string (ProductString)
        str2: Second string (SKU)
        
    Returns:
        Percentage (0.0 to 1.0) of words from str1 that match str2
    """
    if not str1 or not str2:
        return 0.0
    
    # Extract words from both strings
    words1 = _extract_words(str1)
    words2 = _extract_words(str2)
    
    if not words1:
        return 0.0
    
    # Convert to sets for faster lookup (removes duplicates)
    words1_set = set(words1)
    words2_set = set(words2)
    
    # Count matching words
    matching_words = words1_set.intersection(words2_set)
    match_count = len(matching_words)
    
    # Calculate percentage based on unique words in str1
    total_words = len(words1_set)
    
    if total_words == 0:
        return 0.0
    
    return match_count / total_words


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate word-based similarity between two strings.
    Returns the percentage of words from str1 that match words in str2.
    
    Args:
        str1: First string (ProductString)
        str2: Second string (SKU)
        
    Returns:
        Similarity score between 0.0 and 1.0 (percentage of matching words)
    """
    return _calculate_word_match_percentage(str1, str2)


def find_best_sku_match(product_string: str, available_items: List[Dict[str, Any]], 
                        threshold: float = 0.5) -> Optional[Tuple[str, float, Dict[str, Any]]]:
    """
    Find the best matching SKU for a ProductString.
    
    Priority:
    1. First check Products database for existing ProductString -> SKU mapping
    2. If found, verify SKU exists in available_items (by matching SKU's Name) and return match
    3. If not found, use fuzzy word-based matching
    
    Args:
        product_string: ProductString from PO Line Item
        available_items: List of QuickBooks items, each with Id, Name, Sku, Type, Description
        threshold: Minimum similarity threshold for fuzzy matching (0.0 to 1.0)
        
    Returns:
        Tuple of (sku, similarity_score, item_data) or None if no match found
        similarity_score will be 1.0 for database matches, or fuzzy match score for fuzzy matches
    """
    if not product_string or not available_items:
        return None
    
    # Special debug logging for specific ProductString from good-eggs-po-PO_GE351293.pdf
    TARGET_PRODUCT_STRING = "Chana Masala Roti Paratha (8 oz)"
    is_target = product_string == TARGET_PRODUCT_STRING or product_string.strip() == TARGET_PRODUCT_STRING
    
    if is_target:
        print("=" * 80)
        print(f"🔍 DEBUG [good-eggs-po-PO_GE351293.pdf] Starting SKU matching for ProductString: '{product_string}'")
        print("=" * 80)
    
    # STEP 1: Check Products database for existing ProductString -> SKU mapping
    mapped_sku = get_sku_for_product_string(product_string)
    
    if is_target:
        print(f"📦 Step 1 Result: mapped_sku='{mapped_sku}'")
    
    if mapped_sku:
        # Get SKU info from database to get the Name
        skus_data = get_all_skus()
        sku_info = skus_data.get(mapped_sku, {})
        sku_name = sku_info.get("name")
        sku_id = sku_info.get("id")
        
        if is_target:
            print(f"📦 Step 2: Looking up SKU info from Products database")
            print(f"   mapped_sku='{mapped_sku}'")
            print(f"   SKU info found: {sku_info}")
            print(f"   SKU name in DB: '{sku_name}'")
            print(f"   SKU ID in DB: '{sku_id}'")
            print(f"   Available SKU keys in DB: {list(skus_data.keys())[:10]}")
            print(f"   Available QuickBooks items to check: {len(available_items)}")
        
        # If SKU info is missing (name/id are None), try to find it in available_items
        # This can happen if the mapping was created before SKU metadata was populated
        if (not sku_name or not sku_id) and available_items:
            if is_target:
                print(f"⚠️  SKU info incomplete, searching in QuickBooks items to populate...")
            
            for item in available_items:
                item_sku = item.get("Sku") or item.get("SKU") or item.get("sku")
                item_name = item.get("Name") or ""
                
                # Check if mapped_sku matches this item (by SKU or Name)
                if (item_sku and item_sku == mapped_sku) or (item_name and item_name == mapped_sku):
                    # Found the item - update sku_name and sku_id
                    if not sku_name:
                        sku_name = item_name
                    if not sku_id:
                        sku_id = item.get("Id")
                    
                    if is_target:
                        print(f"✅ Found item in QuickBooks, updated: name='{sku_name}', id='{sku_id}'")
                    break
        
        # Find the item in available_items that matches this SKU
        # The mapped_sku could be:
        # 1. The SKU field value from QuickBooks
        # 2. The Name field value (if SKU field was empty)
        # So we need to check both possibilities
        
        if is_target:
            print(f"🔎 Step 3: Searching through QuickBooks items for match...")
        
        for idx, item in enumerate(available_items):
            item_sku = item.get("Sku") or item.get("SKU") or item.get("sku")
            item_name = item.get("Name") or ""
            item_id = item.get("Id") or ""
            
            if is_target and idx < 5:  # Log first 5 items for debugging
                print(f"   Item {idx}: SKU='{item_sku}', Name='{item_name}', Id='{item_id}'")
            
            # Check if mapped_sku matches the item's SKU field
            if item_sku and item_sku == mapped_sku:
                if is_target:
                    print(f"✅ MATCH FOUND (Test A: SKU field match)")
                    print(f"   Operator: item_sku == mapped_sku")
                    print(f"   item_sku='{item_sku}' == mapped_sku='{mapped_sku}'")
                    print(f"   Returning match with similarity=1.0")
                    print("=" * 80)
                return (mapped_sku, 1.0, item)
            
            # Check if mapped_sku matches the item's Name field
            # This handles the case where the SKU identifier in DB is actually the Name
            if item_name and item_name == mapped_sku:
                if is_target:
                    print(f"✅ MATCH FOUND (Test B: Name field match)")
                    print(f"   Operator: item_name == mapped_sku")
                    print(f"   item_name='{item_name}' == mapped_sku='{mapped_sku}'")
                    print(f"   Returning match with similarity=1.0")
                    print("=" * 80)
                return (mapped_sku, 1.0, item)
            
            # Also check if the SKU's Name from DB matches the item's Name
            # This handles the case where mapped_sku is the SKU field, but we need to match by Name
            if sku_name and item_name and item_name == sku_name:
                if is_target:
                    print(f"✅ MATCH FOUND (Test C: SKU's Name match)")
                    print(f"   Operator: item_name == sku_name")
                    print(f"   item_name='{item_name}' == sku_name='{sku_name}'")
                    print(f"   Returning match with similarity=1.0")
                    print("=" * 80)
                return (mapped_sku, 1.0, item)
            
            # Also check by ID if available
            if sku_id and item_id and item_id == sku_id:
                if is_target:
                    print(f"✅ MATCH FOUND (Test D: ID match)")
                    print(f"   Operator: item_id == sku_id")
                    print(f"   item_id='{item_id}' == sku_id='{sku_id}'")
                    print(f"   Returning match with similarity=1.0")
                    print("=" * 80)
                return (mapped_sku, 1.0, item)
        
        if is_target:
            print(f"❌ NO MATCH FOUND in QuickBooks items")
            print(f"   Database mapping exists: ProductString -> SKU='{mapped_sku}'")
            print(f"   But no QuickBooks item found matching this SKU")
            print(f"   Tests performed:")
            print(f"   A. item_sku == mapped_sku")
            print(f"   B. item_name == mapped_sku")
            print(f"   C. item_name == sku_name (from DB)")
            print(f"   D. item_id == sku_id (from DB)")
            print(f"   Total items checked: {len(available_items)}")
            if len(available_items) > 0:
                sample_item = available_items[0]
                sample_sku = sample_item.get("Sku") or sample_item.get("SKU") or sample_item.get("sku")
                sample_name = sample_item.get("Name")
                print(f"   Sample item structure - SKU='{sample_sku}', Name='{sample_name}'")
            print("=" * 80)
    
    # STEP 2: No database mapping found, use fuzzy matching
    best_match = None
    best_score = 0.0
    
    for item in available_items:
        # Try matching against SKU first (if available)
        sku = item.get("Sku") or item.get("SKU") or item.get("sku")
        item_name = item.get("Name") or ""
        
        # Calculate similarity with SKU
        if sku:
            sku_score = _calculate_similarity(product_string, sku)
            if sku_score > best_score:
                best_score = sku_score
                best_match = (sku, sku_score, item)
        
        # Also try matching against item name
        if item_name:
            name_score = _calculate_similarity(product_string, item_name)
            # Prefer SKU matches, but use name if it's better
            if name_score > best_score:
                best_score = name_score
                # Use SKU if available, otherwise use name as identifier
                identifier = sku if sku else item_name
                best_match = (identifier, name_score, item)
    
    # Return match if above threshold
    if best_match and best_score >= threshold:
        return best_match
    
    return None


def match_products_to_skus(product_strings: List[str], available_items: List[Dict[str, Any]], 
                           threshold: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """
    Match multiple ProductStrings to SKUs.
    
    Args:
        product_strings: List of ProductStrings from PO Line Items
        available_items: List of QuickBooks items
        threshold: Minimum similarity threshold
        
    Returns:
        Dictionary mapping ProductString to match info:
        {
            "sku": str or None,
            "similarity": float,
            "matched": bool,
            "item": dict or None
        }
    """
    results = {}
    
    for product_string in product_strings:
        match = find_best_sku_match(product_string, available_items, threshold)
        
        if match:
            sku, similarity, item = match
            results[product_string] = {
                "sku": sku,
                "similarity": similarity,
                "matched": True,
                "item": item
            }
        else:
            results[product_string] = {
                "sku": None,
                "similarity": 0.0,
                "matched": False,
                "item": None
            }
    
    return results

