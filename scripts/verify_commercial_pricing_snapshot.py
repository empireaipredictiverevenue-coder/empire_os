#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.commercial_pricing_live_verifier import (
    refresh_pricing_verification,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_pricing_verification(args.repo_root)
    print(json.dumps({
        "ok": payload["pricing_matches_approved_policy"],
        "expected_product_count": payload["expected_product_count"],
        "drift_count": payload["drift_count"],
        "missing_product_count": payload["missing_product_count"],
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0 if payload["pricing_matches_approved_policy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
