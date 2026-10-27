#!/usr/bin/env python3
"""Optional read-only Awin programme membership review."""
from __future__ import annotations
import argparse
import json
from empire_os.awin_publisher_api import review

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    result = review(write=args.write)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "AWIN_API_MEMBERSHIP_REVIEW_VERIFIED" else 2

if __name__ == "__main__":
    raise SystemExit(main())
