from pathlib import Path
from paypal2quickbooks.core.pdf_parser import parse_pdf
from paypal2quickbooks.core.invoice_mapper import map_to_quickbooks
from paypal2quickbooks.core.csv_writer import write_csv

def convert_directory(input_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for pdf in input_dir.glob("*.pdf"):
        parsed = parse_pdf(pdf)
        qb_invoice = map_to_quickbooks(parsed)
        out_file = output_dir / (pdf.stem + ".csv")
        write_csv(out_file, qb_invoice)
        count += 1
    return count
