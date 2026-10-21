"""Read-only publisher-page preflight of two exact Birmingham roofing sources.

No source admission, editorial signoff, prospect mining or CRM update.
"""
from __future__ import annotations

import argparse
import json

from empire_os.research.brokerage_candidate_source_preflight import (
    run_birmingham_roofing_candidates,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    result = run_birmingham_roofing_candidates()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["original_candidate_pages_observed"] == 2 else 3


if __name__ == "__main__":
    raise SystemExit(main())
