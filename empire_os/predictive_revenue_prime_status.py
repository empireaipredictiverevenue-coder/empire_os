"""Founder-only PRIME source status, composed from existing OBSERVE sources.

Never returns property, prospect, account, contact, permit, buyer or event IDs.
The endpoint is mounted only through the private Founder service's existing
Predictive Cloud status router, not the public hub.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.permit_product_integration import build_permit_product_runtime
from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review

SCHEMA = "empire.predictive_revenue.prime_source_review.v2"


def read_prime_founder_status(
    *, repo_root: Path,
    as_of: datetime | None = None,
    tenant_id: str = "empire-internal",
    official_nws_source_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read existing internal sources and render only safe aggregate metadata.

    The internal tenant identifier is a known system-owned projection, NOT
    authorization for an arbitrary end-user tenant. Do not accept a tenant
    query parameter on the HTTP route.
    """
    now = as_of or datetime.now(timezone.utc)
    safe = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "READ_ONLY_EVIDENCE_HOLD",
        "storm_snapshot_available": False,
        "storm_snapshot_freshness": "NOT_CONNECTED",
        "storm_opportunity_count": None,
        "permit_observation_count": None,
        "official_nws_review_status": "NOT_CONNECTED",
        "official_nws_source_reference_count": None,
        "official_nws_source_freshness": "UNKNOWN",
        "official_nws_is_commercial_opportunity": False,
        "permit_source_blockers": ["SOURCE_REVIEW_UNAVAILABLE"],
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
    try:
        storm_file = repo_root / "runtime/storm_opportunity/latest.json"
        try:
            raw = json.loads(storm_file.read_text(encoding="utf-8"))
            storm = raw if isinstance(raw, dict) else None
        except (OSError, ValueError, UnicodeError):
            storm = None
        permit = build_permit_product_runtime(
            repo_root, tenant_id=tenant_id, as_of=now,
        )
        review = build_predictive_revenue_brain_review(
            tenant_id=tenant_id, as_of=now,
            storm_snapshot=storm,
            permit_integration=permit,
            crm_deals=(), churn_signals=(), simulate_pipeline=False,
            official_nws_source_review=official_nws_source_review,
        )
        safe.update({
            "storm_snapshot_available": storm is not None,
            "official_nws_review_status": review["official_source_observatory"]["status"],
            "official_nws_source_reference_count": review["official_source_observatory"]["source_references_reviewed"],
            "official_nws_source_freshness": review["official_source_observatory"]["freshness"],
            "storm_snapshot_freshness": review["source_freshness"]["storm_snapshot"],
            "storm_opportunity_count": len(review["storm_research"]),
            "permit_observation_count": len(review["permit_research"]),
            "permit_source_blockers": list(permit.blockers),
        })
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        # Fail CLOSED on malformed source/scope/trust: never convert missing,
        # stale or corrupt evidence to an apparent "zero opportunities".
        safe["status"] = "READ_ONLY_SOURCE_REVIEW_UNAVAILABLE"
    return safe
