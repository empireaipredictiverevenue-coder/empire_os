"""Private, read-only sanity check against existing EmpireOS runtime sources.

Never reads connected CRM/finance datasets or submits messages. Only prints
aggregate counts and provenance/authority metadata, not tenant record details.
Run from the feature worktree with PYTHONPATH pointed at this checkout.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.permit_product_integration import build_permit_product_runtime
from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review


def review_root_sources(*, repo_root: Path, tenant_id: str, as_of: datetime) -> dict:
    storm_file = repo_root / "runtime/storm_opportunity/latest.json"
    try:
        raw = json.loads(storm_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("storm snapshot not mapping")
        storm = raw
        storm_present = True
    except (OSError, ValueError, UnicodeError):
        storm = None
        storm_present = False

    permit = build_permit_product_runtime(
        repo_root, tenant_id=tenant_id, as_of=as_of,
    )
    review = build_predictive_revenue_brain_review(
        tenant_id=tenant_id, as_of=as_of,
        storm_snapshot=storm, permit_integration=permit,
        crm_deals=(), churn_signals=(), simulate_pipeline=False,
    )

    return {
        "schema_version": "empire.predictive_revenue.prime_source_review.v1",
        "status": "READ_ONLY_EVIDENCE_HOLD",
        "mode": "OBSERVE",
        "storm_snapshot_available": storm_present,
        "storm_snapshot_freshness": review["source_freshness"]["storm_snapshot"],
        "storm_opportunity_count": len(review["storm_research"]),
        "permit_observation_count": len(review["permit_research"]),
        "permit_source_blockers": list(permit.blockers),
        "crm_status": "NOT_CONNECTED_NOT_A_VERIFIED_ZERO",
        "prime_simulation_status": "NOT_RUN_NO_VERIFIED_CRM_INPUT",
        "churn_status": "NOT_CONNECTED_NO_INTERVENTIONS",
        "source_custody_independently_verified": False,
        "buyer_demand_verified": False,
        "revenue_verified": False,
        "realized_revenue_cents": None,
        "actual_payments_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="/srv/empire_os")
    parser.add_argument("--tenant-id", default="empire-internal")
    args = parser.parse_args()
    result = review_root_sources(
        repo_root=Path(args.source_root), tenant_id=args.tenant_id,
        as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
