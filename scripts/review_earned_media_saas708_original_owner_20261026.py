"""Read-only 700->708 exact original ASTRA website owner acceptance.

Expected result while root backup/independent owner receipt absent: held exit 2.
There is intentionally NO --apply or publication command.
"""
from __future__ import annotations
import argparse
import json

from empire_os.earned_media_saas708_owner_preflight import review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, action="store_true")
    parser.parse_args(argv)
    report = review()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].startswith("OWNER_EVIDENCE_COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
