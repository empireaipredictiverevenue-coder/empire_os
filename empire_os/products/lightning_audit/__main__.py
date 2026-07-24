"""Entry point for lightning audit."""
from empire_os.products.lightning_audit import audit
import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--out", default="/tmp/lightning_audit.json")
a = ap.parse_args()
res = audit(a.url)
Path(a.out).write_text(json.dumps(res, indent=2))
print(f"wrote {a.out}")
