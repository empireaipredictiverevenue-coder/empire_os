"""Private read-only operator for Predictive customer needs and value hypotheses."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_customer_value_demand import (
    build_cross_market_customer_value_research_blueprint,
    review_existing_community_needs_runtime,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--include-research-blueprint", action="store_true")
    args = parser.parse_args()
    result = review_existing_community_needs_runtime(
        args.repo_root, as_of=datetime.now(timezone.utc),
    )
    if args.include_research_blueprint:
        result["unexecuted_cross_market_research_blueprint"] = (
            build_cross_market_customer_value_research_blueprint()
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
