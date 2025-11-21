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

                        # Spatial extraction for "ATTN:" (Address)
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
        data = {
            "source_file": filename,
            "customer": "Unknown",
            "customer_address": "Unknown",
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
        
        # 2. PO Number
        # Try specific patterns first
        po_patterns = [
            r"(?:PO|Order)\s*(?:#|Number|No\.?)?\s*[:.]?\s*([A-Za-z0-9-_]+)",
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
        
        # Fallback: Look for label on one line and value on the next
        if data["po_number"] == "Unknown":
            for i, line in enumerate(lines):
                clean_line = line.strip().lower()
                # Check if line looks like a header containing PO info
                if re.search(r"(?:po|purchase order)\s*(?:#|number|no\.?)?", clean_line):
                    # Check next line
                    if i + 1 < len(lines):
                        next_line = lines[i+1].strip()
                        # Split next line into tokens
                        tokens = next_line.split()
                        # Look for a token that looks like a PO number (not a date, alphanumeric)
                        for token in tokens:
                            # Skip dates
                            if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", token):
                                continue
                            # Skip common words
                            if token.lower() in ["net", "30", "terms", "date"]:
                                continue
                            
                            if len(token) > 2 and re.search(r"\d", token): # Must have at least one digit
                                data["po_number"] = token
                                break
                        if data["po_number"] != "Unknown":
                            break

        # 3. Dates
        # Heuristic: Look for lines containing "Date"
        # If line has "Date" but not "Delivery" -> Order Date
        # If line has "Date" and "Delivery" -> Delivery Date
        
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        
        # 3. Dates
        # Heuristic: Look for lines containing "Date"
        # If line has "Date" but not "Delivery" -> Order Date
        # If line has "Date" and "Delivery" -> Delivery Date
        # Handle case where label is on one line and value is on the next
        
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if "date" in lower_line:
                # Determine type based on THIS line (the label line)
                is_delivery = "delivery" in lower_line
                
                # Look for date value in THIS line
                dates_in_line = re.findall(date_pattern, line)
                
                # If not found, look in NEXT line
                if not dates_in_line and i + 1 < len(lines):
                    next_line = lines[i+1]
                    dates_in_line = re.findall(date_pattern, next_line)
                
                if dates_in_line:
                    date_val = dates_in_line[0]
                    
                    if is_delivery:
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

        # 4. Addresses (Heuristic: Look for "Bill To" and "Ship To")
        lower_text = text.lower()
        
        def extract_address_block(start_keyword):
            start_idx = -1
            for i, line in enumerate(lines):
                if start_keyword in line.lower():
                    start_idx = i
                    break
            if start_idx != -1:
                # Take next 3 lines, stopping if we hit another keyword or empty line
                addr = []
                for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
                    l = lines[j]
                    if any(k in l.lower() for k in ["ship to:", "bill to:", "item", "qty", "total"]):
                        break
                    addr.append(l)
                return ", ".join(addr)
            return "Unknown"

        # Address (Bill To)
        if attn_text:
            attn_lines = [l.strip() for l in attn_text.split('\n') if l.strip()]
            # Remove "ATTN:" from the first line if present
            if attn_lines:
                attn_lines[0] = re.sub(r"ATTN:?", "", attn_lines[0], flags=re.IGNORECASE).strip()
            
            addr_parts = []
            for line in attn_lines:
                lower_line = line.lower()
                # Stop at keywords
                if any(k in lower_line for k in ["date:", "po #", "vendor", "ship to"]):
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
                data["customer_address"] = ", ".join(addr_parts)
            else:
                data["customer_address"] = "Unknown"
        else:
            data["customer_address"] = extract_address_block("bill to")
        
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
                    if any(k in lower_line for k in ["terms", "net 30", "order qty", "unit cost", "amount", "total", "requested", "r e q u e s t e d"]):
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
                    data["delivery_address"] = ", ".join(addr_parts)
                else:
                    data["delivery_address"] = "Unknown"
        else:
            data["delivery_address"] = extract_address_block("ship to")

        # Fallback: If Address (Bill To) is unknown but Delivery Address (Ship To) is known, use Delivery Address
        if (data["customer_address"] == "Unknown" or not data["customer_address"]) and data["delivery_address"] != "Unknown":
            data["customer_address"] = data["delivery_address"]

        # 5. Items (Try to find a table with Qty/Rate/Amount)
        items_found = False
        
        # Method A: pdfplumber tables
        if tables:
            for table in tables:
                if not table: continue
                # DEBUG: Print raw table
                # console.print(f"DEBUG TABLE: {table}")
                
                header = [str(c).lower() for c in table[0] if c]
                if any(x in header for x in ["qty", "quantity", "description", "item", "amount", "price"]):
                    # Identify columns
                    qty_idx = -1
                    desc_idx = -1
                    price_idx = -1
                    rate_idx = -1
                    
                    for i, col in enumerate(header):
                        if "qty" in col or "quantity" in col:
                            qty_idx = i
                        elif "description" in col or "item" in col or "product" in col:
                            desc_idx = i
                        elif "amount" in col or "total" in col:
                            price_idx = i
                        elif "rate" in col or "price" in col or "unit" in col:
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

        # Method B: Text-based line item extraction (fallback)
        if not items_found:
            # Look for lines that end with a number (amount) and have other numbers (qty, rate)
            # Regex: Description ... Qty ... Rate ... Amount
            # Or: Item ... Qty ... Rate ... Amount
            
            # Find where items might start (after header)
            start_scanning = False
            for line in lines:
                if any(x in line.lower() for x in ["item", "description", "qty", "quantity"]):
                    start_scanning = True
                    continue
                
                if start_scanning:
                    # Stop if we hit total
                    if "total" in line.lower():
                        break
                        
                    # Try to parse line
                    # Look for at least 2 numbers
                    # This regex looks for: (Description) (Number) (Number) (Number optional)
                    # It's tricky. Let's try to find all numbers in the line.
                    
                    # Remove currency symbols
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
                    
                    if len(nums) >= 3:
                        # Assume: Qty, Rate, Amount (last 3 numbers usually, or Qty, Rate -> Amount)
                        # If 3 nums: Qty, Rate, Amount
                        qty = nums[-3]
                        rate = nums[-2]
                        price = nums[-1]
                        desc = " ".join(text_parts)
                        
                        # Sanity check: qty * rate approx price
                        if abs(qty * rate - price) < 0.1:
                             data["items"].append({
                                "product_name": desc,
                                "quantity": qty,
                                "rate": rate,
                                "price": price
                            })
                    elif len(nums) == 2:
                        # Assume Qty, Rate (calculate Amount)
                        # Or Rate, Amount?
                        # Let's assume Qty, Rate if they are smallish?
                        # Hard to guess. Let's assume Qty is first.
                        qty = nums[0]
                        rate = nums[1]
                        price = qty * rate
                        desc = " ".join(text_parts)
                        data["items"].append({
                                "product_name": desc,
                                "quantity": qty,
                                "rate": rate,
                                "price": price
                            })


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
