#!/usr/bin/env python3
"""Optional Awin observer within the original governed Gmail evidence cycle."""
from __future__ import annotations
import argparse
import json
from empire_os.awin_publisher_operations import run

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = run(write=args.write)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "AWIN_NETWORK_APPROVED_PROGRAMME_APPLICATIONS_PENDING_REVIEW" else 2

if __name__ == "__main__":
    raise SystemExit(main())
