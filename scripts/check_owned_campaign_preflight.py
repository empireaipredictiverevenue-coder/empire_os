#!/usr/bin/env python3
"""Print a read-only audit; never rewrite the department snapshot or deploy."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from empire_os.owned_campaign_preflight import inspect_campaigns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "runtime/astra/department_cycle_latest.json")
    parser.add_argument("--infrastructure-review", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    review = json.loads(args.infrastructure_review.read_text())
    result = inspect_campaigns(snapshot["marketing_growth"], review)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["campaigns_blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
