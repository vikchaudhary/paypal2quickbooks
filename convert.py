import PyPDF2
import re
import csv
from datetime import datetime
from pathlib import Path

# --------- PDF TEXT EXTRACTION (PyPDF2 only, per your request) ---------
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            t = page.extract_text() or ''
            text += t + "\n"
    return text

# --------- ITEM PARSER (matches your provided layout) ---------
# Input after header looks like sequence of blocks, e.g.:
# 1
# Chicken Tikka Masala with Kati Roll Bento Box
# includes complimentary Samosa with Tamarind Chutney
# 35
# $26.00
# $910.00
# (then next item: 2, description, ...)

def _parse_items_paypal(items_text: str, join_delim: str = " | "):
    """Parse PayPal items by scanning blocks structured as:
      [item_number]\n
      [one or more description lines]\n
      [optional: "<qty> x $<rate> | ..."]\n
      [qty-only integer]\n
      [$<rate>]\n
      [$<amount>]
    Description lines are joined with join_delim.
    Per-line tax is the sum of $ amounts on the qtyx line if it mentions 'tax'.
    """
    print("-" * 80)

    # Normalize/clean lines, keep non-empty for predictable scanning
    raw_lines = [ln.strip() for ln in items_text.splitlines()]
    lines = [ln for ln in raw_lines if ln != ""]

    items = []
    i = 0

    # Regex helpers
    item_no_re  = re.compile(r"^(?:[1-9]|10)$")         # item number on its own line
    qty_only_re = re.compile(r"^\d+$")                   # e.g., 35
    money_re    = re.compile(r"^\$([\d,]+\.\d{2})$")   # e.g., $26.00
    qtyx_re     = re.compile(r"^(?P<qty>\d+)\s*x\s*\$?(?P<rate>[\d,]+\.\d{2})(?P<rest>.*)$", re.IGNORECASE)
    totals_re   = re.compile(r"^(Subtotal|TOTAL|Amount paid|AMOUNT DUE)\b", re.IGNORECASE)

    def to_float_str(x: str) -> str:
        return x.replace(',', '')

    while i < len(lines):
        ln = lines[i]
        if totals_re.search(ln):
            break

        # Find an item number line first
        if not item_no_re.match(ln):
            i += 1
            continue

        item_number = ln
        i += 1

        # Collect description lines until we encounter qtyx or qty-only/money/totals
        desc_parts = []
        qtyx_line = None
        qty_from_qtyx = None
        rate_from_qtyx = None

        while i < len(lines):
            cur = lines[i]
            if totals_re.search(cur):
                break
            # qtyx line (e.g., "35 x $26.00 | SSF Sales Tax 9.875% ($89.86)")
            m_qtyx = qtyx_re.match(cur)
            if m_qtyx:
                qtyx_line = cur
                qty_from_qtyx = m_qtyx.group('qty')
                rate_from_qtyx = to_float_str(m_qtyx.group('rate'))
                i += 1
                # Do not include qtyx line in description
                break
            # Stop description if next lines are structure fields
            if qty_only_re.match(cur) or money_re.match(cur):
                break
            # Otherwise treat as description text
            desc_parts.append(cur)
            i += 1

        description = join_delim.join(desc_parts).strip()

        # Next: qty-only, price, amount (each optional, if present)
        qty = None
        rate = None
        amount = None

        # qty-only integer line
        if i < len(lines) and qty_only_re.match(lines[i]):
            qty = lines[i]
            i += 1

        # price line: $xx.xx
        if i < len(lines) and money_re.match(lines[i]):
            rate = money_re.match(lines[i]).group(1)
            i += 1

        # amount line: $xx.xx
        if i < len(lines) and money_re.match(lines[i]):
            amount = money_re.match(lines[i]).group(1)
            i += 1

        # Fill missing fields using qtyx or computation
        if qty is None and qty_from_qtyx is not None:
            qty = qty_from_qtyx
        if rate is None and rate_from_qtyx is not None:
            rate = rate_from_qtyx
        if amount is None:
            # Try to take last $... from qtyx line (often the extended amount inside parentheses)
            if qtyx_line:
                dollars = re.findall(r"\$([\d,]+\.\d{2})", qtyx_line)
                if dollars:
                    amount = to_float_str(dollars[-1])
        if amount is None and qty and rate and qty.isdigit():
            try:
                amount = f"{float(to_float_str(rate)) * int(qty):.2f}"
            except Exception:
                amount = "0.00"

        # Per-line tax from qtyx line when it mentions 'tax'
        tax_total = 0.0
        if qtyx_line and 'tax' in qtyx_line.lower():
            for m in re.findall(r"\$([\d,]+\.\d{2})", qtyx_line):
                try:
                    tax_total += float(to_float_str(m))
                except Exception:
                    pass

        items.append({
            'item_number': item_number,
            'description': description,
            'quantity': str(qty or '1'),
            'rate': to_float_str(rate or '0.00'),
            'amount': to_float_str(amount or '0.00'),
            'tax_amount': f"{tax_total:.2f}",
        })

    print(f"No. of items extracted: {len(items)}")
    return items

# --------- HIGH-LEVEL INVOICE PARSER ---------

def _grab_after_label_block(text: str, label: str) -> str:
    """Given a label that may be followed by blank lines and/or a line that is just ':',
    return the first non-empty, non-':' line that follows it. Case-insensitive."""
    lines = text.splitlines()
    lab = label.strip().lower()
    for i, ln in enumerate(lines):
        if ln.strip().lower() == lab:
            j = i + 1
            while j < len(lines) and (lines[j].strip() == '' or lines[j].strip() == ':'):
                j += 1
            return lines[j].strip() if j < len(lines) else ''
    return ''

def _norm_date_mdy(s: str) -> str:
    s = s.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y")
        except Exception:
            pass
    return ''

def parse_invoice_data(text: str):
    print("Starting parse_invoice_data()")
    data = {}

    # normalize spacing but keep newlines
    text = text.replace('\t', ' ')
    text = re.sub(r' +', ' ', text)

    # print("First 500 chars of PDF text (after normalization):")
    # print(text[:500])
    # print("\n" + "="*50 + "\n")

    # Invoice meta (multiline-friendly: label, then optional blank/':' lines, then value)
    data['invoice_number'] = _grab_after_label_block(text, 'Invoice No#')
    print(f"Invoice Number: {data['invoice_number']}")

    inv_date_raw = _grab_after_label_block(text, 'Invoice Date')
    data['invoice_date'] = _norm_date_mdy(inv_date_raw) if inv_date_raw else ''
    print(f"Invoice Date: {data['invoice_date']}")

    due_date_raw = _grab_after_label_block(text, 'Due Date')
    data['due_date'] = _norm_date_mdy(due_date_raw) if due_date_raw else ''
    print(f"Due Date: {data['due_date']}")

    # BILL TO (best-effort)
    bill_to = re.search(r'BILL TO\s+(.*?)(?=SHIP TO|Subtotal|Tax|Tip|TOTAL)', text, re.DOTALL)
    if bill_to:
        bill_lines = [l.strip() for l in bill_to.group(1).split('\n') if l.strip()]
        print(f"BILL TO lines: {bill_lines}")
        data['customer_name']  = bill_lines[0] if len(bill_lines) > 0 else ''
        data['contact_person'] = bill_lines[1] if len(bill_lines) > 1 else ''
        data['address_line1']  = bill_lines[2] if len(bill_lines) > 2 else ''
        data['address_line2']  = bill_lines[3] if len(bill_lines) > 3 else ''
        data['customer_email'] = bill_lines[4] if len(bill_lines) > 4 else ''
    else:
        print("WARNING: BILL TO section not found!")
        for k in ['customer_name','contact_person','address_line1','address_line2','customer_email']:
            data[k] = ''

    # SHIP TO (best-effort)
    ship_to = re.search(r'SHIP TO\s+(.*?)(?=Subtotal|Tax|Tip|TOTAL)', text, re.DOTALL)
    if ship_to:
        ship_lines = [l.strip() for l in ship_to.group(1).split('\n') if l.strip()]
        print(f"\nSHIP TO lines: {ship_lines}")
        data['ship_to_name']     = ship_lines[0] if len(ship_lines)>0 else ''
        data['ship_to_contact']  = ship_lines[1] if len(ship_lines)>1 else ''
        data['ship_to_address1'] = ', '.join(ship_lines[2:]) if len(ship_lines)>2 else ''
        data['ship_to_address2'] = ''
        data['ship_to_email']    = ''
    else:
        print("WARNING: SHIP TO section not found!")
        for k in ['ship_to_name','ship_to_contact','ship_to_address1','ship_to_address2','ship_to_email']:
            data[k] = ''

    # Totals
    def find_money(label):
        m = re.search(label + r'\s+\$?([\d,]+\.\d{2})', text)
        return m.group(1).replace(',', '') if m else '0.00'

    for field in ['Subtotal','Tax','Tip','TOTAL','Amount paid','AMOUNT DUE']:
        print(f"Parsing field: {field}")

    data['subtotal']    = find_money('Subtotal')
    data['tax']         = find_money('Tax')
    data['tip']         = find_money('Tip')
    data['total']       = find_money('TOTAL')
    data['amount_paid'] = find_money('Amount paid')
    data['amount_due']  = find_money('AMOUNT DUE')

    # --------- (A) Start items right after the header block QTY/HRS → PRICE → AMOUNT($) ---------
    hdr = re.search(r'(?:^|\n)\s*QTY/HRS\s*(?:\n)+\s*PRICE\s*(?:\n)+\s*AMOUNT\(\$\)\s*', text)
    if hdr:
        start_idx  = hdr.end()
        items_text = text[start_idx:]
        #print("Items section found via QTY/HRS–PRICE–AMOUNT($) header.")
        #print("# ITEMS & DESCRIPTION QTY/HRS PRICE AMOUNT($)")
        #print("-" * 80)
        #print(items_text.strip())  # dump the remainder so you can see what's parsed
        data['line_items'] = _parse_items_paypal(items_text)
    else:
        # Fallback: legacy header
        items_section = re.search(r'#\s*ITEMS\s*&\s*DESCRIPTION.*', text, re.DOTALL)
        if items_section:
            print("Items section found (fallback # ITEMS & DESCRIPTION)")
            data['line_items'] = _parse_items_paypal(items_section.group(0))
        else:
            print("WARNING: Items section not found!")
            data['line_items'] = []

    print(f"No. of items parsed: {len(data['line_items'])}")
    return data

# --------- CSV WRITER (unchanged output columns) ---------
def create_quickbooks_csv(invoice_data_list, output_file='quickbooks_import.csv'):
    headers = ['Invoice Number','Customer','Contact Person','Address Line 1','Address Line 2','Customer Email',
               'Ship To Name','Ship To Contact','Ship To Address 1','Ship To Address 2','Ship To Email','Invoice Date',
               'Due Date','Item Number','Item Description','Quantity','Item Rate','Item Amount','Tax Amount',
               'Tip Amount','Total Amount','Amount Paid','Balance Due']
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for data in invoice_data_list:
            line_items = data.get('line_items', [])
            print("\n" + "="*80)
            print("EXTRACTED LINE ITEMS (mapped to PDF columns):")
            print("="*80)
            print(f"{'#':<5} {'ITEMS & DESCRIPTION':<40} {'QTY/HRS':<10} {'PRICE':<12} {'AMOUNT($)':<12}")
            print("-"*80)

            for i, item in enumerate(line_items):
                print(f"{item.get('item_number',''):<5} {item.get('description','')[:40]:<40} {item.get('quantity',''):<10} ${item.get('rate','')} ${item.get('amount','')}")
                writer.writerow([
                    data.get('invoice_number',''), data.get('customer_name',''), data.get('contact_person',''),
                    data.get('address_line1',''), data.get('address_line2',''), data.get('customer_email',''),
                    data.get('ship_to_name',''), data.get('ship_to_contact',''), data.get('ship_to_address1',''),
                    data.get('ship_to_address2',''), data.get('ship_to_email',''), data.get('invoice_date',''), data.get('due_date',''), item.get('item_number',''), item.get('description',''),
                    item.get('quantity',''), item.get('rate',''), item.get('amount',''), item.get('tax_amount',''),
                    data.get('tip','0.00') if i==len(line_items)-1 else '',
                    data.get('total','0.00') if i==len(line_items)-1 else '',
                    data.get('amount_paid','0.00') if i==len(line_items)-1 else '',
                    data.get('amount_due','0.00') if i==len(line_items)-1 else ''
                ])

            print("-"*80)
            print(f"Total items extracted: {len(line_items)}")
            print(f"Subtotal: ${data.get('subtotal','0.00')}")
            print(f"Tax: ${data.get('tax','0.00')}")
            print(f"Tip: ${data.get('tip','0.00')}")
            print(f"Total: ${data.get('total','0.00')}")
            print("="*80)
    print(f"\n✓ QuickBooks CSV created: {output_file}")

# --------- RUNNERS ---------
def process_single_pdf(pdf_path):
    print(f"Processing: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    invoice_data = parse_invoice_data(text)
    output_csv = Path(pdf_path).stem + '.csv'
    create_quickbooks_csv([invoice_data], output_csv)
    print(f"  ✓ Extracted invoice #{invoice_data.get('invoice_number','N/A')}")
    print(f"  ✓ Created: {output_csv}")
    return True

def process_pdf_directory(directory_path):
    pdf_files = list(Path(directory_path).glob('*.pdf'))
    if not pdf_files:
        print(f"No PDF files found in {directory_path}")
        return
    print(f"Processing {len(pdf_files)} PDF file(s)...\n")
    success_count = 0
    for pdf_file in pdf_files:
        if process_single_pdf(pdf_file):
            success_count += 1
        print()
    print(f"Successfully processed {success_count} of {len(pdf_files)} invoice(s)")

if __name__ == '__main__':
    process_pdf_directory('.')
