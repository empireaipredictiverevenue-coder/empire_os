"""Current read-only brokerage research & editorial owner evidence inspection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.research.brokerage_editorial_review import review_brokerage_editorial

ORIGINAL_US_SAMPLE = Path(
    "/home/ubuntu/empire_worktrees/agency_acquisition_conversion_20261020/"
    "docs/integrations/agency_acquisition/original_market_samples/"
    "LINCOLN_PARK_IMPLANTS_PUBLIC_EVIDENCE_SAMPLE_20261020.md"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--country", required=True, choices=("US", "GB"))
    args = parser.parse_args()
    receipt = review_brokerage_editorial(
        args.country,
        original_sample=ORIGINAL_US_SAMPLE if args.country == "US" else None,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "ORIGINAL_SOURCE_PAGES_INSPECTED_EDITORIAL_PENDING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
