from pathlib import Path
from typing import Any, Dict

def parse_pdf(pdf_path: Path) -> Dict[str, Any]:
    return {"source": pdf_path.name}
