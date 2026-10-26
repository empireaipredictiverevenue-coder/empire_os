"""Read-only original ASTRA release-owner gate, revised two-route/eight-asset release."""
from __future__ import annotations

import argparse
import json

from empire_os.earned_media_saas670_owner_preflight import review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, action="store_true")
    args = parser.parse_args(argv)
    result = review()
    print(json.dumps(result, sort_keys=True))
    # Held status is expected until exact founder, ASTRA and root receipts exist.
    return 0 if result["status"].startswith("OWNER_EVIDENCE_COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
