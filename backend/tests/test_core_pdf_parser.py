from pathlib import Path
from paypal2quickbooks.core.pdf_parser import parse_pdf

def test_parse_pdf_placeholder(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 placeholder")
    result = parse_pdf(pdf)
    assert "source" in result
