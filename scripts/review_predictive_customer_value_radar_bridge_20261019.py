"""Read-only customer needs -> live Opportunity Radar -> value-pilot preflight."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_customer_value_radar_bridge import (
    review_customer_value_radar_bridge_runtime,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    result = review_customer_value_radar_bridge_runtime(
        args.repo_root, as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
