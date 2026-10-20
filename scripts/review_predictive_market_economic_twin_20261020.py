"""Read-only actual source availability for future Predictive Market Economic Twins."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_market_economic_source_readiness import (
    review_market_economic_source_readiness_runtime,
)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
    args=parser.parse_args()
    result=review_market_economic_source_readiness_runtime(
        args.repo_root,as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
