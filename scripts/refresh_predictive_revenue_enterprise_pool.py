from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.predictive_revenue_enterprise_pool import refresh

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="/srv/empire_os")
    p.add_argument("--limit", type=int, default=25)
    args = p.parse_args()
    payload = refresh(Path(args.repo_root), limit=args.limit)
    print(json.dumps({
        "seed_target_count": payload["seed_target_count"],
        "eligible_rolling_candidate_count": payload["eligible_rolling_candidate_count"],
        "rolling_addition_count": payload["rolling_addition_count"],
        "total_enterprise_candidate_count": payload["total_enterprise_candidate_count"],
        "outreach_authorized": payload["outreach_authorized"],
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
