import csv
import sys
from pathlib import Path

def validate(path: Path) -> bool:
    required = {"InvoiceNumber"}
    with path.open() as f:
        reader = csv.DictReader(f)
        return required.issubset(set(reader.fieldnames or []))

if __name__ == "__main__":
    ok = validate(Path(sys.argv[1]))
    print("valid" if ok else "invalid")
    raise SystemExit(0 if ok else 1)
