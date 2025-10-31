import csv
import sys
from pathlib import Path

def load_total(path: Path) -> float:
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                return float(row.get("Total", "0") or "0")
            except ValueError:
                return 0.0
    return 0.0

if __name__ == "__main__":
    actual = load_total(Path(sys.argv[1]))
    expected = load_total(Path(sys.argv[2]))
    print(f"actual={actual} expected={expected}")
    raise SystemExit(0 if abs(actual - expected) < 1e-6 else 1)
