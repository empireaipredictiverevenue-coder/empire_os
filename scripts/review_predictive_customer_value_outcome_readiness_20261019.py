"""Read-only production aggregate check for Predictive customer-value outcomes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_customer_value_outcome_readiness import (
    review_customer_value_outcome_readiness_runtime,
)


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only", action="store_true",required=True)
    p.add_argument("--repo-root",default="/srv/empire_os")
    args=p.parse_args()
    result=review_customer_value_outcome_readiness_runtime(
        args.repo_root,as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED" else 2


if __name__=="__main__":
    raise SystemExit(main())
