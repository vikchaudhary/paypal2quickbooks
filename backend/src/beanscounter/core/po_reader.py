import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pdfplumber
import pytesseract
from PIL import Image
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

class POReader:
    def __init__(self):
        pass

    def scan_directory(self, path: Path) -> List[Path]:
        """Find all supported PO files in the directory."""
        extensions = {".pdf", ".png", ".jpg", ".jpeg"}
        return [p for p in path.iterdir() if p.suffix.lower() in extensions and p.is_file()]

    def extract_data(self, file_path: Path) -> Dict[str, Any]:
        """Extract structured data from a PO file."""
        text = ""
        ship_to_text = ""
        attn_text = ""
        tables = []
        
        try:
            if file_path.suffix.lower() == ".pdf":
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
                        extracted_tables = page.extract_tables()
                        if extracted_tables:
                            tables.extend(extracted_tables)
                        
                        # Spatial extraction for "Ship To"
                        if not ship_to_text:
                            matches = page.search("Ship To", case=False)
                            if matches:
                                for match in matches:
                                    x0 = match['x0'] - 10
                                    top = match['bottom']
                                    x1 = page.width
                                    bottom = top + 200
                                    try:
                                        crop = page.crop((x0, top, x1, bottom))
                                        ship_to_text = crop.extract_text()
                                    except Exception:
                                        pass

                        # Spatial extraction for "ATTN:" (Address) - fallback if Bill To not found
                        if not attn_text:
                            matches = page.search("ATTN:", case=False)
                            if matches:
                                for match in matches:
                                    # Crop from the start of "ATTN:" to capture the whole line, then we'll strip "ATTN:"
                                    x0 = match['x0']
                                    top = match['top'] - 2 # Capture the line properly
                                    # Limit width to avoid right column (Date/PO)
                                    x1 = match['x0'] + 300 
                                    bottom = top + 150
                                    try:
                                        crop = page.crop((x0, top, x1, bottom))
                                        attn_text = crop.extract_text()
                                    except Exception:
                                        pass

            else:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                # Image table extraction is hard without specialized tools, skipping for now
        except Exception as e:
            console.print(f"[red]Error reading {file_path.name}: {e}[/red]")
            return {}

        return self._parse_text(text, tables, file_path.name, ship_to_text, attn_text)

    def _parse_text(self, text: str, tables: List[List[List[str]]], filename: str, ship_to_text: str = "", attn_text: str = "") -> Dict[str, Any]:
        """Heuristic parsing of text and tables."""
        # Company domain to exclude from customer emails
        COMPANY_DOMAIN = "indianbento.com"
        
        data = {
            "source_file": filename,
            "customer": "Unknown",
            "customer_address": "Unknown",
            "customer_email": "Unknown",
            "po_number": "Unknown",
            "order_date": "Unknown",
            "delivery_date": "Unknown",
            "invoice_amount": 0.0,
            "delivery_address": "Unknown",
            "total_amount": "Unknown",
            "items": []
        }


        lines = text.split('\n')
        # DEBUG: Print raw text
        # console.print(f"DEBUG TEXT:\n{text}")
        
        # 1. Customer Name (Heuristic: First non-empty line usually, or from Ship To)
        # We'll refine this later with spatial data
        if data["customer"] == "Unknown":
            for line in lines:
                clean_line = line.strip()
                if not clean_line: continue
                # Skip common headers
                if any(x in clean_line.lower() for x in ["purchase order", "invoice", "bill to", "ship to", "page", "date", "po #"]):
                    continue
                # Skip lines that look like dates or numbers
                if re.match(r"^[\d\s\-\/\.]+$", clean_line):
                    continue
                
                # Assume this is the vendor/customer name
                data["customer"] = clean_line
                break

        # 2. PO Number
        # Try specific patterns first
        po_patterns = [
            # Allow spaces within PO number, but not at the end (e.g., "MB-PFS-IBE251125 TUE")
            # Use [ \t] instead of \s to avoid matching newlines
            r"(?:PO|Order)[ \t]*(?:#|Number|No\.?)?[ \t]*[:.]?[ \t]*([A-Za-z0-9][A-Za-z0-9-_]*(?:[ \t]+[A-Za-z0-9]+)?)\b",
            r"PO[_-][\d]+",
        ]
        for pat in po_patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                if match.lastindex:
                    val = match.group(1)
                    val = val.strip()
                    # Clean up leading separators
                    val = val.lstrip("_-")
                    # Check if it's just a label word and has digits
                    if val.lower() not in ["po", "order", "number", "no", "no.", "invoice", "date", "attn", "attn:"]:
                        if len(val) > 2 and any(c.isdigit() for c in val):
                            data["po_number"] = val
                            break
            if data["po_number"] != "Unknown":
                break
        
        # Fallback: Look for label on one line and value on the next few lines
        if data["po_number"] == "Unknown":
            for i, line in enumerate(lines):
                clean_line = line.strip().lower()
                # Check if line looks like a header containing PO info
                # Require "#" or "number" to avoid matching document titles like "PURCHASE ORDER"
                if re.search(r"(?:po|purchase order)\s*(?:#|number|no\.)", clean_line):
                    # Check next few lines (not just immediate next line)
                    # Collect all candidate tokens, then pick the best one
                    candidates = []
                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line = lines[j].strip()
                        if not next_line:
                            continue
                        # Split next line into tokens
                        tokens = next_line.split()
                        for token in tokens:
                            # Skip dates
                            if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", token):
                                continue
                            # Skip common words
                            if token.lower() in ["net", "30", "terms", "date", "united", "states"]:
                                continue
                            
                            if len(token) > 2 and re.search(r"\d", token): # Must have at least one digit
                                # Add to candidates with priority score
                                priority = 0
                                if "_" in token or "-" in token:
                                    priority = 2  # High priority
                                elif token.startswith("PO") or token.startswith("po"):
                                    priority = 1  # Medium priority
                                candidates.append((priority, token))
                    
                    # Select the best candidate (highest priority)
                    if candidates:
                        candidates.sort(key=lambda x: x[0], reverse=True)
                        data["po_number"] = candidates[0][1]
                        break


        # 3. Dates
        # Heuristic: Look for lines containing "Date"
        # If line has "Date" but not "Delivery" -> Order Date
        # If line has "Date" and "Delivery" -> Delivery Date
        # Handle case where label is on one line and value is on the next
        
        # Date patterns: numeric dates and full format like "Tue Nov 25, 2025"
        full_date_pattern = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}"
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        
        for i, line in enumerate(lines):
            lower_line = line.lower()
            # Check for Date OR Delivery keywords
            if any(k in lower_line for k in ["date", "delivery", "ship", "due"]):
                # Determine type based on THIS line (the label line)
                is_delivery = any(k in lower_line for k in ["delivery", "ship", "due"])
                
                # Look for date value in THIS line - try full format first, then numeric
                full_dates_in_line = re.findall(full_date_pattern, line)
                dates_in_line = re.findall(date_pattern, line) if not full_dates_in_line else []
                
                # If not found, look in NEXT line
                if not full_dates_in_line and not dates_in_line and i + 1 < len(lines):
                    next_line = lines[i+1]
                    full_dates_in_line = re.findall(full_date_pattern, next_line)
                    if not full_dates_in_line:
                        dates_in_line = re.findall(date_pattern, next_line)
                
                # Prefer full date format over numeric
                date_val = full_dates_in_line[0] if full_dates_in_line else (dates_in_line[0] if dates_in_line else None)
                
                if date_val:
                    if is_delivery:
                        # Avoid overwriting if we already found one, unless this one looks better?
                        # For now, just take the first one we find
                        if data["delivery_date"] == "Unknown":
                            data["delivery_date"] = date_val
                    else:
                        # Assume Order Date if not already set
                        # We prioritize the first "Date" label we find for Order Date
                        if data["order_date"] == "Unknown":
                            data["order_date"] = date_val
        
        # Fallback: if we didn't find them with specific labels, try just finding all dates
        if data["order_date"] == "Unknown" or data["delivery_date"] == "Unknown":
             all_dates = re.findall(date_pattern, text)
             if all_dates:
                 if data["order_date"] == "Unknown":
                     data["order_date"] = all_dates[0]
                 if data["delivery_date"] == "Unknown":
                     if len(all_dates) > 1:
                         data["delivery_date"] = all_dates[1]
                     else:
                         data["delivery_date"] = all_dates[0]
        
        # Fallback: if we didn't find them with specific labels, try just finding all dates
        if data["order_date"] == "Unknown" or data["delivery_date"] == "Unknown":
             all_dates = re.findall(date_pattern, text)
             if all_dates:
                 if data["order_date"] == "Unknown":
                     data["order_date"] = all_dates[0]
                 if data["delivery_date"] == "Unknown":
                     if len(all_dates) > 1:
                         data["delivery_date"] = all_dates[1]
                     else:
                         data["delivery_date"] = all_dates[0]

        # 3b. Ordered By
        if data.get("ordered_by", "Unknown") == "Unknown":
            for line in lines:
                if "ordered by" in line.lower() or "buyer" in line.lower() or "requester" in line.lower():
                    # Extract value after colon or just end of line
                    parts = re.split(r"[:\t]", line, 1)
                    if len(parts) > 1:
                        val = parts[1].strip()
                        if val:
                            data["ordered_by"] = val
                            break

        # 4. Addresses (Heuristic: Look for "Bill To" and "Ship To")
        lower_text = text.lower()
        
        def extract_address_block(start_keyword):
            start_idx = -1
            for i, line in enumerate(lines):
                if start_keyword in line.lower():
                    start_idx = i
                    break
            if start_idx != -1:
                # Take next lines, stopping if we hit another keyword or empty line
                addr = []
                for j in range(start_idx + 1, min(start_idx + 8, len(lines))):
                    l = lines[j]
                    # Stop at keywords that indicate end of address block
                    if any(k in l.lower() for k in ["ship to:", "bill to:", "item", "qty", "total", "delivery:", "account #", "po #", "po#", "terms:", "ordered by:", "product code", "item name", "extended cost"]):
                        break
                    if not l.strip():
                        continue
                    addr.append(l)
                return "\n".join(addr)
            return "Unknown"

        # Address (Bill To)
        # Special handling: sometimes "Bill To" and "Ship To" are on the same line
        # Try to extract "Bill To: <name>" from the same line first
        bill_to_found = False
        if not attn_text:
            # First, check if Bill To is on the same line as Ship To
            for line in lines:
                if "bill to" in line.lower():
                    # Try to extract text after "Bill To:"
                    match = re.search(r"Bill To:\s*(.+?)(?:Ship To|Nutrition|$)", line, re.IGNORECASE)
                    if match:
                        bill_to_name = match.group(1).strip()
                        if bill_to_name:
                            data["customer_address"] = bill_to_name
                            bill_to_found = True
                            break
            
            # If not found on same line, find Bill To and Ship To positions in the text
            if not bill_to_found:
                bill_to_idx = -1
                ship_to_idx = -1
                for i, line in enumerate(lines):
                    if "bill to" in line.lower() and bill_to_idx == -1:
                        bill_to_idx = i
                    if "ship to" in line.lower() and ship_to_idx == -1:
                        ship_to_idx = i
                
                # Extract address between Bill To and Ship To (or next section)
                if bill_to_idx != -1:
                    addr = []
                    end_idx = ship_to_idx if ship_to_idx > bill_to_idx else min(bill_to_idx + 8, len(lines))
                    for j in range(bill_to_idx + 1, end_idx):
                        l = lines[j]
                        # Stop at keywords
                        if any(k in l.lower() for k in ["ship to", "delivery:", "account #", "po #", "po#", "terms:", "ordered by:", "status:", "product code", "item name"]):
                            break
                        if not l.strip():
                            continue
                        addr.append(l.strip())
                    
                    if addr:
                        data["customer_address"] = "\n".join(addr)
                        bill_to_found = True
        
        if attn_text and not bill_to_found:
            attn_lines = [l.strip() for l in attn_text.split('\n') if l.strip()]
            # Remove "Bill To" or "ATTN:" from the first line if present
            if attn_lines:
                attn_lines[0] = re.sub(r"(Bill To|ATTN):?", "", attn_lines[0], flags=re.IGNORECASE).strip()
                # If first line is now empty after removal, skip it
                if not attn_lines[0]:
                    attn_lines = attn_lines[1:]
            
            addr_parts = []
            for line in attn_lines:
                lower_line = line.lower()
                # Stop at keywords
                if any(k in lower_line for k in ["date:", "po #", "po#", "vendor", "ship to", "delivery:", "account #", "product code", "item name"]):
                    break
                if not line.strip():
                    continue
                
                addr_parts.append(line)

                # Check if this line contains a country name, if so, stop here
                if any(c in lower_line for c in ["united states", "usa", "u.s.a"]):
                    break
                if re.search(r"\bus\b", lower_line):
                    break
            
            if addr_parts:
                data["customer_address"] = "\n".join(addr_parts)
                bill_to_found = True
        
        if not bill_to_found:
            # Try to find "Bill To:" specifically (with colon) first
            bill_to_addr = extract_address_block("bill to:")
            if bill_to_addr == "Unknown":
                # Fallback to generic "bill to"
                bill_to_addr = extract_address_block("bill to")
            data["customer_address"] = bill_to_addr
        
        # Use spatial extraction for Ship To if available
        if ship_to_text:
            ship_lines = [l.strip() for l in ship_to_text.split('\n') if l.strip()]
            # Skip "Ship To" header if present
            if ship_lines and "ship to" in ship_lines[0].lower():
                ship_lines = ship_lines[1:]
            
            if ship_lines:
                # Check if first line is a customer name or address start (starts with digit)
                is_address_line = ship_lines[0][0].isdigit()
                
                if not is_address_line:
                    data["customer"] = ship_lines[0]
                    start_idx = 1
                else:
                    data["customer"] = "Unknown"
                    start_idx = 0
                
                # Rest is address
                addr_parts = []
                for line in ship_lines[start_idx:]:
                    # Stop if we hit keywords indicating end of address block
                    lower_line = line.lower()
                    if any(k in lower_line for k in ["terms", "net 30", "order qty", "unit cost", "amount", "total", "requested", "r e q u e s t e d", "product code", "item name", "extended cost"]):
                        break
                    
                    addr_parts.append(line)
                    
                    # Check if this line contains a country name, if so, stop here
                    # "United States", "US", "USA", "U.S.A", "U.S.A."
                    # Use word boundary check or simple substring for now, given the request
                    if any(c in lower_line for c in ["united states", "usa", "u.s.a"]):
                        break
                    # specific check for "us" as a whole word to avoid matching inside words
                    if re.search(r"\bus\b", lower_line):
                        break
                
                if addr_parts:
                    data["delivery_address"] = "\n".join(addr_parts)
                else:
                    data["delivery_address"] = "Unknown"
        else:
            data["delivery_address"] = extract_address_block("ship to")

        # Fallback: If Address (Bill To) is unknown but Delivery Address (Ship To) is known, use Delivery Address
        if (data["customer_address"] == "Unknown" or not data["customer_address"]) and data["delivery_address"] != "Unknown":
            data["customer_address"] = data["delivery_address"]
        
        # Fallback: If customer name is still Unknown, try to extract from Bill To address
        if data["customer"] == "Unknown" and data["customer_address"] != "Unknown":
            # Extract first line of customer_address as customer name
            first_line = data["customer_address"].split('\n')[0].strip()
            if first_line and not first_line[0].isdigit():  # Make sure it's not an address line starting with a number
                data["customer"] = first_line

        # 5. Items (Try to find a table with Qty/Rate/Amount)
        items_found = False
        
        # Method A: pdfplumber tables
        if tables:
            for table in tables:
                if not table: continue
                # DEBUG: Print raw table
                # console.print(f"DEBUG TABLE: {table}")
                
                header = [str(c).lower() for c in table[0] if c]
                # Broaden the check for relevant columns
                if any(x in header for x in ["qty", "quantity", "units", "count", "description", "item", "product", "material", "sku", "amount", "price", "rate", "cost", "total"]):
                    # Identify columns
                    qty_idx = -1
                    desc_idx = -1
                    price_idx = -1
                    rate_idx = -1
                    
                    for i, col in enumerate(header):
                        if any(k in col for k in ["qty", "quantity", "units", "count"]):
                            qty_idx = i
                        elif any(k in col for k in ["description", "item", "product", "material", "sku", "details"]):
                            desc_idx = i
                        elif any(k in col for k in ["amount", "total", "ext price", "extended"]):
                            price_idx = i
                        elif any(k in col for k in ["rate", "price", "unit", "cost"]):
                            rate_idx = i
                    
                    if desc_idx != -1:
                        # items_found = True # Don't set this yet, wait until we actually get an item
                        for row in table[1:]:
                            # Skip empty rows
                            if not any(row): continue
                            
                            # Extract data
                            desc = row[desc_idx] if desc_idx < len(row) and row[desc_idx] else ""
                            
                            qty = 0.0
                            if qty_idx != -1 and qty_idx < len(row) and row[qty_idx]:
                                try:
                                    qty_str = str(row[qty_idx]).lower().replace('ea', '').strip()
                                    qty = float(qty_str)
                                except ValueError:
                                    pass
                            
                            # Debug individual row parsing if needed
                            # if qty == 0.0:
                            #    console.print(f"DEBUG ROW: {row} -> Qty parsed as 0.0")

                            rate = 0.0
                            if rate_idx != -1 and rate_idx < len(row) and row[rate_idx]:
                                try:
                                    rate = float(str(row[rate_idx]).replace('$', '').replace(',', ''))
                                except ValueError:
                                    pass
                            
                            price = 0.0
                            if price_idx != -1 and price_idx < len(row) and row[price_idx]:
                                try:
                                    price = float(str(row[price_idx]).replace('$', '').replace(',', ''))
                                except ValueError:
                                    pass
                            
                            # If price wasn't found but qty and rate were, calculate it
                            if price == 0.0 and qty > 0 and rate > 0:
                                price = qty * rate
                            
                            # Only add if we have a description and at least one numeric value
                            if desc and (qty > 0 or rate > 0 or price > 0):
                                data["items"].append({
                                    "product_name": desc,
                                    "quantity": qty,
                                    "rate": rate,
                                    "price": price
                                })

                                items_found = True

        # Method A.2: Specific UCSF Table Extraction (Header-based)
        if not items_found:
            # Look for the specific header: "Product Code Item Name Qty Size Cost Extended Cost"
            # Note: "Extended Cost" might be on two lines in the PDF text representation, 
            # but let's look for "Product Code" and "Item Name" on the same line.
            header_idx = -1
            for i, line in enumerate(lines):
                if "product code" in line.lower() and "item name" in line.lower() and "qty" in line.lower():
                    header_idx = i
                    break
            
            if header_idx != -1:
                # Found the header, parse subsequent lines
                for j in range(header_idx + 1, len(lines)):
                    line = lines[j].strip()
                    if not line: continue
                    
                    # Stop at totals
                    if "grand total" in line.lower() or "total" in line.lower():
                        break
                        
                    # Parse row
                    # Format: COLD-SAAG Veg,IndianBento,PunjabiSaagPaneer,5lb 4EACH (5 Pounds) $ 40.75 $ 163.00
                    # The "4EACH" is a common issue where space is missing.
                    
                    # Regex to capture the components
                    # 1. Product Code (start of line, non-space)
                    # 2. Item Name (text until we hit the Qty/Size part)
                    # 3. Qty (digits)
                    # 4. Size (text)
                    # 5. Cost (currency)
                    # 6. Extended Cost (currency)
                    
                    # Try to split by the known structure at the end of the line first (Cost, Ext Cost)
                    # Look for "$ <number> $ <number>" at the end
                    
                    # Regex for the end of the line: $ 40.75 $ 163.00
                    # Allow for spaces between $ and number
                    end_pattern = r"\$\s*([\d,]+\.\d{2})\s*\$\s*([\d,]+\.\d{2})$"
                    end_match = re.search(end_pattern, line)
                    
                    if end_match:
                        rate = float(end_match.group(1).replace(",", ""))
                        price = float(end_match.group(2).replace(",", ""))
                        
                        # Remove the matched part from the line
                        remaining = line[:end_match.start()].strip()
                        
                        # Now look for Qty and Size at the end of 'remaining'
                        # Expecting: "4EACH (5 Pounds)" or "4 EACH (5 Pounds)"
                        # Regex: (\d+)\s*([A-Za-z]+.*)$
                        
                        # Find the last digit sequence in the remaining string which is likely the Qty
                        # But be careful about digits in Item Name.
                        # Usually Qty is followed by Unit/Size.
                        
                        # Let's try to find the Qty which is a number followed by 'EACH' or similar
                        qty_match = re.search(r"(\d+)\s*(EACH.*)$", remaining, re.IGNORECASE)
                        
                        if qty_match:
                            qty = float(qty_match.group(1))
                            # size = qty_match.group(2) # We don't need size for now
                            
                            # Everything before Qty is Product Code + Item Name
                            prod_info = remaining[:qty_match.start()].strip()
                            
                            # Split Product Code and Item Name
                            # Product Code is usually the first word
                            parts = prod_info.split(None, 1)
                            if len(parts) == 2:
                                product_code = parts[0]
                                item_name = parts[1]
                                full_name = f"{product_code} {item_name}"
                            else:
                                full_name = prod_info
                                
                            data["items"].append({
                                "product_name": full_name,
                                "quantity": qty,
                                "rate": rate,
                                "price": price
                            })
                            items_found = True

        # Method B: Text-based line item extraction (fallback)
        if not items_found:
            # Look for lines that end with a number (amount) and have other numbers (qty, rate)
            
            # 1. Try to find a header line to start scanning
            start_scanning = False
            header_keywords = ["item", "description", "qty", "quantity", "product", "material", "service", "part", "sku", "details", "unit price", "amount", "price"]
            
            potential_items = []
            
            for i, line in enumerate(lines):
                lower_line = line.lower()
                
                # Check if this is a header line
                if not start_scanning:
                    if any(x in lower_line for x in header_keywords):
                        # Make sure it's not just a random line with one of these words
                        # It should ideally have at least two of these words or look like a header
                        match_count = sum(1 for x in header_keywords if x in lower_line)
                        if match_count >= 1:
                            start_scanning = True
                            continue
                
                # Stop scanning if we hit totals or notes
                if "total" in lower_line and "subtotal" not in lower_line and len(line) < 40:
                     # This might be the total line, stop here? 
                     # But sometimes "Total" is in the description. 
                     # Usually Total is at the start of the line or distinct.
                     if re.match(r"^\s*total", lower_line):
                         start_scanning = False
                         break
                
                # If we are scanning, or if we haven't found a header but the line looks like an item
                # (We'll filter later)
                
                # Remove currency symbols and commas for parsing numbers
                clean_line = line.replace("$", "").replace(",", "")
                parts = clean_line.split()
                
                nums = []
                text_parts = []
                for p in parts:
                    try:
                        val = float(p)
                        nums.append(val)
                    except ValueError:
                        text_parts.append(p)
                
                # Heuristic: An item line usually has a description and at least one price-like number
                # It shouldn't be a date line
                if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", line):
                    continue
                    
                desc = " ".join(text_parts)
                
                # Filter out obvious non-item lines
                if len(desc) < 3: continue
                if any(x in desc.lower() for x in ["page", "phone", "fax", "email", "bill to", "ship to"]): continue
                
                item_data = None
                
                if len(nums) >= 3:
                    # Qty, Rate, Amount
                    qty = nums[-3]
                    rate = nums[-2]
                    price = nums[-1]
                    
                    # Stricter sanity checks
                    # 1. Qty should be reasonable (< 10000)
                    # 2. Rate should be reasonable (< $1000)
                    # 3. Price should match qty * rate (within 1% tolerance) OR be reasonable (< $100000)
                    if qty < 10000 and rate < 1000:
                        calculated_price = qty * rate
                        price_matches = abs(calculated_price - price) < max(0.1, calculated_price * 0.01)
                        price_reasonable = price < 100000
                        
                        if price_matches or (price_reasonable and price > 0):
                            item_data = {"product_name": desc, "quantity": qty, "rate": rate, "price": price}
                        
                elif len(nums) == 2:
                    # Qty, Rate or Rate, Amount?
                    # Assume Qty, Rate -> Price
                    qty = nums[0]
                    rate = nums[1]
                    
                    # Sanity checks
                    if qty < 10000 and rate < 1000:
                        price = qty * rate
                        if price < 100000:
                            item_data = {"product_name": desc, "quantity": qty, "rate": rate, "price": price}
                    
                elif len(nums) == 1:
                    # Just Amount/Price?
                    # This is very likely to be a partial line or garbage
                    # Only accept if:
                    # 1. Price is reasonable (< $500)
                    # 2. Description looks like a product (has letters, not just numbers/symbols)
                    # 3. Description is not too short (> 10 chars)
                    price = nums[0]
                    
                    # Check if description looks valid
                    has_letters = any(c.isalpha() for c in desc)
                    desc_long_enough = len(desc) > 10
                    price_reasonable = 0.01 < price < 500
                    
                    # Additional check: description shouldn't start with common non-product patterns
                    desc_lower = desc.lower()
                    looks_like_continuation = desc_lower.startswith(('oz)', '--', 'and', 'with', 'the'))
                    
                    if has_letters and desc_long_enough and price_reasonable and not looks_like_continuation:
                        item_data = {"product_name": desc, "quantity": 1, "rate": price, "price": price}

                if item_data:
                    if start_scanning:
                        data["items"].append(item_data)
                    else:
                        potential_items.append(item_data)
            
            # If we didn't find items via header scanning, use the potential ones
            # but filter them strictly
            if not data["items"] and potential_items:
                # Use potential items if they look reasonable
                # e.g. they are contiguous or look like a block
                data["items"] = potential_items


        # 6. Invoice Amount
        if data["items"]:
            data["invoice_amount"] = sum(item["price"] for item in data["items"])
        else:
            amount_match = re.search(r"Total\s*(?:Amount)?\s*[:.]?\s*\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
            if amount_match:
                try:
                    data["invoice_amount"] = float(amount_match.group(1).replace(",", ""))
                except:
                    pass

        # 7. Customer Email
        # Extract all email addresses from the text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Filter out company domain emails
        customer_emails = [email for email in emails if COMPANY_DOMAIN not in email.lower()]
        
        if customer_emails:
            # Define generic finance team email prefixes (in order of priority)
            finance_prefixes = ['ap@', 'finance@', 'accounts@', 'billing@', 'orders@', 
                              'accounting@', 'payable@', 'accountspayable@', 'invoices@']
            
            # First, try to find a generic finance team email
            for prefix in finance_prefixes:
                for email in customer_emails:
                    if email.lower().startswith(prefix):
                        data["customer_email"] = email
                        break
                if data["customer_email"] != "Unknown":
                    break
            
            # If no finance email found, use the first customer email
            if data["customer_email"] == "Unknown":
                data["customer_email"] = customer_emails[0]

        # 8. Try to match domain to company name if customer name is missing
        if data.get("customer") == "Unknown" and data.get("customer_email") and data["customer_email"] != "Unknown":
            try:
                from beanscounter.services.domain_matching_service import get_company_name_from_email
                # Try to get QB client, but don't fail if not configured
                qb_client = None
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
                except Exception:
                    # QB not configured, continue without it
                    pass
                
                suggested_name = get_company_name_from_email(data["customer_email"], qb_client)
                if suggested_name:
                    data["customer"] = suggested_name
            except Exception as e:
                # If domain matching fails, keep customer as "Unknown"
                print(f"Domain matching failed: {e}")

        return data

    def print_invoice(self, data: Dict[str, Any]):
        """Print formatted invoice data."""
        console.print(Panel(f"[bold blue]Invoice Data: {data['source_file']}[/bold blue]"))
        
        console.print(f"Customer: [green]{data.get('customer', 'Unknown')}[/green]")
        console.print(f"Customer Address: [green]{data.get('customer_address', 'Unknown')}[/green]")
        console.print(f"PO Number: [blue]{data.get('po_number', 'Unknown')}[/blue]")
        console.print(f"[bold]Order Date:[/bold] {data['order_date']}")
        console.print(f"[bold]Delivery Date:[/bold] {data['delivery_date']}")
        console.print(f"[bold]Delivery Address:[/bold] {data['delivery_address']}")
        
        table = Table(title="Line Items")
        table.add_column("Product", style="cyan")
        table.add_column("Qty", justify="right")
        table.add_column("Rate", justify="right")
        table.add_column("Price", justify="right")

        for item in data["items"]:
            table.add_row(
                item["product_name"],
                str(item["quantity"]),
                f"${item['rate']:.2f}",
                f"${item['price']:.2f}"
            )

        console.print(table)
        console.print(f"[bold green]Total Amount: ${data['invoice_amount']:.2f}[/bold green]\n")

def main():
    reader = POReader()
    
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path(".")

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = reader.scan_directory(input_path)
    else:
        console.print(f"[red]Invalid path: {input_path}[/red]")
        return
    
    if not files:
        console.print("[yellow]No PO files (PDF/Image) found.[/yellow]")
        return

    console.print(f"[bold]Found {len(files)} files to process...[/bold]\n")
    
    for file_path in files:
        data = reader.extract_data(file_path)
        if data:
            reader.print_invoice(data)

if __name__ == "__main__":
    main()
