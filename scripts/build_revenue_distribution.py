#!/usr/bin/env python3
"""Build the OBSERVE-only Revenue Distribution artifact; never activate work."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.revenue_distribution import refresh_revenue_distribution


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--generated-at", help="Timezone-aware observation time for deterministic replay")
    parser.add_argument("--acquisition-budget-cents", type=int, default=None)
    args = parser.parse_args()
    payload = refresh_revenue_distribution(args.repo_root.resolve(), generated_at=args.generated_at, acquisition_budget_cents=args.acquisition_budget_cents)
    print(json.dumps({"mode": payload["mode"], "opportunities": len(payload["opportunities"]), "proposals": len(payload["distribution_actions"]), "blockers": payload["blockers"], "authority": payload["authority"], "human_review_count": len(payload["human_review_queue"]), "person_bound_count": sum(row["person_verified"] for row in payload["human_review_queue"]), "review_blockers": payload["review_blockers"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
