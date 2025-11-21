from pathlib import Path
from typing import Dict, Any
import csv

def write_csv(path: Path, invoice: Dict[str, Any]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(invoice.keys()))
        writer.writeheader()
        writer.writerow(invoice)
