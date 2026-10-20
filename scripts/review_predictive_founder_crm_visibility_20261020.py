"""Founder CRM visibility bridge, isolated from privileged canonical source checks."""
from __future__ import annotations

import argparse
import json

from empire_os.predictive_existing_founder_crm_bridge import run_existing_founder_crm_review


def main() -> int:
    parser = argparse.ArgumentParser(description="Reuse existing read-only founder CRM reader")
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    report = run_existing_founder_crm_review()
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    # A missing source is a structured OBSERVE hold, not a broken release.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
