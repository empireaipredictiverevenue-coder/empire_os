#!/usr/bin/env python3
"""Refresh canonical account evidence through to review-only opportunity briefs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from empire_os.competitor_account_brief import (
    build_account_brief_batch,
    write_account_brief_snapshot,
)
from empire_os.competitor_audience_research_executor import (
    execute_snapshot_research,
    write_account_research_snapshot,
)
from empire_os.competitor_audience_runtime import (
    refresh_competitor_audience_snapshot,
)
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)
from empire_os.competitor_call_source_watch import refresh as refresh_call_source_watch
from empire_os.competitor_call_alert_precision import refresh as refresh_alert_precision
from empire_os.opportunity_brief import (
    materialize_opportunity_briefs,
    write_opportunity_briefs,
)


def refresh_bounded_competitor_watch(
    repo_root: Path,
    *,
    watch_fn: Callable[[Path], dict[str, Any]] = refresh_call_source_watch,
) -> dict[str, Any]:
    """Share the existing 15-minute opportunity-brief cadence.

    No new timer, daemon, source roster, DB materializer, or outbound action.
    Never make a failed market observation fail the original opportunity briefs.
    """
    atlas = repo_root / "runtime/competitive_intelligence/call_acquisition_atlas_latest.json"
    if not atlas.is_file() or atlas.is_symlink():
        return {
            "status": "ORIGINAL_OPERATOR_ATLAS_UNAVAILABLE",
            "checked": 0, "execution_authority": "none",
        }
    try:
        result = watch_fn(repo_root)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return {
            "status": "RESEARCH_REFRESH_FAILED",
            "error_type": type(exc).__name__,
            "checked": 0, "execution_authority": "none",
        }
    radar = result.get("commercial_radar", {})
    return {
        "status": "BOUNDED_ORIGINAL_WATCHER_REFRESHED",
        "checked": int(result.get("checked_this_cycle") or 0),
        "source_unavailable_count": len(
            result.get("source_unavailable_this_cycle") or []
        ),
        "radar_status": radar.get("status", "NOT_PUBLISHED"),
        "radar_pending_review_count": int(radar.get("pending_review_count") or 0),
        "radar_new_review_candidate_count": int(radar.get("new_review_candidate_count") or 0),
        "execution_authority": "none",
        "outreach_enabled": False,
    }


def refresh_bounded_alert_precision(
    repo_root: Path,
    *,
    precision_fn: Callable[[Path], dict[str, Any]] = refresh_alert_precision,
) -> dict[str, Any]:
    """Exactly one official NWS detail review in the original 15min cycle.

    It is noncritical; an unavailable feed or permission never interrupts
    the canonical opportunity briefing or enables any outreach/call traffic.
    """
    source = repo_root / "runtime/search_fabric_evidence/geo_opportunity_latest_v68.json"
    if not source.is_file() or source.is_symlink():
        return {
            "status": "ORIGINAL_GEO_OBSERVATION_UNAVAILABLE",
            "checked": 0, "execution_authority": "none",
        }
    try:
        result = precision_fn(repo_root)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return {
            "status": "COUNTY_ZONE_RESEARCH_HELD",
            "error_type": type(exc).__name__,
            "checked": 0, "execution_authority": "none",
        }
    return {
        "status": result.get("last_fetch_status", "UNKNOWN"),
        "checked": int(result.get("detail_checked_this_cycle") or 0),
        "official_detail_observation_count": int(
            result.get("official_detail_observation_count") or 0
        ),
        "county_ugc_area_count": int(result.get("county_ugc_area_count") or 0),
        "forecast_zone_area_count": int(result.get("forecast_zone_area_count") or 0),
        "geographic_precision": "NWS_COUNTY_OR_FORECAST_UGC_NOT_HOMEOWNER_ZIP",
        "buyer_territory_or_homeowner_lead_verified": False,
        "execution_authority": "none",
    }


def refresh_opportunity_brief_chain(
    repo_root: str | Path,
    *,
    writer: PostgresIntelligenceMaterializer | None = None,
    search_fn: Callable[..., Any] | None = None,
    fetch_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    materializer = writer or PostgresIntelligenceMaterializer.from_env()

    audience = refresh_competitor_audience_snapshot(root, materializer)

    research_kwargs: dict[str, Any] = {}
    if search_fn is not None:
        research_kwargs["search_fn"] = search_fn
    if fetch_fn is not None:
        research_kwargs["fetch_fn"] = fetch_fn

    research = execute_snapshot_research(audience, **research_kwargs)
    write_account_research_snapshot(root, research)

    account_briefs = build_account_brief_batch(audience, research)
    write_account_brief_snapshot(root, account_briefs)

    opportunity_briefs = materialize_opportunity_briefs(account_briefs)
    paths = write_opportunity_briefs(root, opportunity_briefs)

    competitor_watch = refresh_bounded_competitor_watch(root)
    alert_precision = refresh_bounded_alert_precision(root)

    return {
        "competitor_change_radar": competitor_watch,
        "call_geographic_precision": alert_precision,
        "schema_version": "empire.opportunity-brief-refresh-chain.v1",
        "mode": "OBSERVE_TO_REVIEW_ONLY",
        "canonical_signal_row_count": int(
            audience.get("canonical_signal_row_count") or 0
        ),
        "canonical_latest_observed_at": audience.get("latest_observed_at"),
        "account_research_generated_at": research.get("generated_at"),
        "account_research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "account_brief_count": int(account_briefs.get("brief_count") or 0),
        "supported_claim_count": int(
            account_briefs.get("supported_claim_count") or 0
        ),
        "blocked_claim_count": int(
            account_briefs.get("blocked_claim_count") or 0
        ),
        "opportunity_brief_count": int(
            opportunity_briefs.get("brief_count") or 0
        ),
        "review_ready_count": int(
            opportunity_briefs.get("review_ready_count") or 0
        ),
        "paths": [str(path) for path in paths],
        "external_send_allowed": False,
        "payment_mutation": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_opportunity_brief_chain(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
