"""Original competitor intelligence: source-bound STATE-LEVEL call-market research.

Consumes the existing Search Fabric NWS observations READ ONLY, plus the
original Lead Smart public ZIP coverage snapshot (guidance, NOT accepted
geography). It never maps alert states down to property addresses/ZIP codes,
ranks customers, or grants call/outbound/payment authorization.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = "empire.competitor_call_geo_research.v1"
GEO = Path("runtime/search_fabric_evidence/geo_opportunity_latest_v68.json")
COVERAGE = Path("runtime/revenue/lead_smart/coverage/latest.json")
DEST = Path("runtime/competitive_intelligence/call_geo_research_latest.json")
STATES = frozenset(("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()))
WATCHED = {"IL": "EXISTING_ROOFING_PILOT_CHICAGO", "CO": "LEGACY_LOCAL_COMPETITOR_RESEARCH_DENVER"}
SOURCE_SCOPE = "NWS_UGC_STATE_ONLY_NOT_ADDRESS_OR_ZIP"


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive timestamp")
    return d.astimezone(timezone.utc)


def _allowed_nws_ref(value: Any) -> bool:
    return (isinstance(value, str)
            and value.startswith("https://api.weather.gov/alerts/")
            and len(value) <= 400
            and "@" not in value and "?" not in value and "#" not in value)


def build_geo_research(*, geo: dict, coverage: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware time required")
    now = now.astimezone(timezone.utc)
    if (geo.get("schema_version") != "empire.search_fabric.geo_opportunity_observation.v68"
            or geo.get("source") != "NOAA_NWS_PUBLIC_ALERTS"
            or geo.get("source_url") != "https://api.weather.gov/alerts/active"
            or geo.get("source_rights_readonly_public_alerts") is not True
            or geo.get("database_writes") is not False
            or geo.get("outbound_sent") is not False
            or geo.get("market_gap_or_competitor_rank_measured") is not False):
        raise ValueError("unauthorised or untrusted geographic observation")
    if (coverage.get("buyer") != "Lead Smart"
            or coverage.get("schema_version") != "empire.lead_smart.coverage_snapshot.v1"
            or coverage.get("mode") != "OBSERVE"
            or coverage.get("source", {}).get("semantics") != "TARGETING_GUIDANCE_ONLY"
            or coverage.get("source", {}).get("payout_guaranteed") is not False):
        raise ValueError("untrusted roofing coverage observation")
    latest_geo = _time(geo.get("retrieved_at_utc"))
    latest_coverage = _time(coverage.get("observed_at"))
    geo_age = (now - latest_geo).total_seconds()
    coverage_age = (now - latest_coverage).total_seconds()
    geo_fresh = 0 <= geo_age <= 7200
    coverage_fresh = 0 <= coverage_age <= 21600
    if not (geo_fresh and coverage_fresh):
        return {
            "schema_version": SCHEMA, "mode": "OBSERVE", "generated_at": now.isoformat(),
            "fresh_for_research": False,
            "geo_source_fresh": geo_fresh, "coverage_source_fresh": coverage_fresh,
            "states": [], "state_count": 0, "active_roofing_alert_count": 0,
            "reason": "SOURCE_SNAPSHOTS_STALE_OR_CLOCK_INVALID",
            "buyer_geo_verified": False, "human_lead_verified": False,
            "call_traffic_authorized": False, "execution_authority": "none",
        }

    rows = coverage.get("rows")
    events = geo.get("geo_events")
    if not isinstance(rows, list) or not isinstance(events, list):
        raise ValueError("missing original source rows")
    if not 1 <= len(rows) <= 40000 or len(events) > 100:
        raise ValueError("unexpected input size")
    if coverage.get("coverage", {}).get("row_count") != len(rows):
        raise ValueError("coverage row-count mismatch")
    if geo.get("research_only_geo_events") != len(events):
        raise ValueError("alert row-count mismatch")
    state_coverage: Counter[str] = Counter()
    unmapped_coverage_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid coverage record")
        state = row.get("state")
        zip_code = row.get("zip")
        if not isinstance(zip_code, str) or not re.fullmatch(r"[0-9]{5}", zip_code):
            raise ValueError("invalid coverage ZIP row")
        # The original nationwide source has 176 valid ZIPs with null state.
        # Retain that uncertainty explicitly; never guess a state from a ZIP.
        if state is None:
            unmapped_coverage_rows += 1
            continue
        if state not in STATES:
            raise ValueError("untrusted ZIP coverage state")
        state_coverage[state] += 1

    by_state: dict[str, list[dict]] = {}
    seen = set()
    for record in events:
        if not isinstance(record, dict):
            raise ValueError("invalid alert observation")
        state = record.get("state")
        if state not in STATES or record.get("geographic_precision") != SOURCE_SCOPE:
            raise ValueError("missing bounded state-only scope")
        digest = record.get("source_event_sha256")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("bad source identity digest")
        if digest in seen:
            continue
        seen.add(digest)
        if not _allowed_nws_ref(record.get("source_record_url")):
            raise ValueError("untrusted NWS source URL")
        if not isinstance(record.get("potential_supply_research_verticals"), list):
            raise ValueError("missing researched verticals")
        issued, expires = _time(record.get("issued_at_utc")), _time(record.get("expires_at_utc"))
        if issued > now or expires <= now or "roofing" not in record["potential_supply_research_verticals"]:
            continue
        by_state.setdefault(state, []).append({
            "event_type": str(record.get("event") or "")[:100],
            "issued_at_utc": issued.isoformat(),
            "expires_at_utc": expires.isoformat(),
            "source_url": record["source_record_url"],
            "source_sha256": digest,
            "geographic_precision": SOURCE_SCOPE,
        })

    candidate_states = set(by_state) | set(WATCHED)
    result = []
    for state in sorted(candidate_states):
        alerts = by_state.get(state, [])
        zip_rows = state_coverage.get(state, 0)
        # A heuristic for which evidence to review FIRST, not probability
        # of a lead, real buyer capacity, predicted payout, or profit.
        # Breadth is a modest RESEARCH convenience, never a measure of
        # active buyer capacity, population, demand or expected revenue.
        breadth = (
            6 if zip_rows >= 1000 else
            4 if zip_rows >= 100 else
            3 if zip_rows >= 75 else
            2 if zip_rows >= 10 else
            1 if zip_rows else 0
        )
        priority_points = (
            (45 if alerts else 0)
            + (20 if zip_rows else 0)
            + (25 if state == "IL" else 10 if state == "CO" else 0)
            + breadth
        )
        # Multiple state-scope warnings do not increase location precision.
        priority_points = min(96, priority_points)
        result.append({
            "state": state,
            "state_level_alerts": len(alerts),
            "alert_evidence": sorted(alerts, key=lambda v: v["source_sha256"]),
            "public_coverage_zip_row_count": zip_rows,
            "priority_points_for_research_only": priority_points,
            "priority_class": (
                "SOURCE_EVENT_AND_COVERAGE_REVIEW" if alerts and zip_rows else
                "SOURCE_EVENT_ONLY_NO_COVERAGE" if alerts else
                "EXISTING_MARKET_BASELINE_NO_MATCHING_ALERT_IN_SAMPLED_SOURCE"
            ),
            "existing_market_context": WATCHED.get(state),
            "observed_geo_precision": SOURCE_SCOPE if alerts else "NONE",
            "exact_alert_zip_match_verified": False,
            "buyer_specific_active_capacity_verified": False,
            "homeowner_intent_or_property_damage_verified": False,
            "payable_call_or_revenue_verified": False,
            "research_next_step": (
                "Obtain geographic detail from official warning/permit sources and confirm buyer-specific ZIP eligibility separately"
                if alerts else
                "Review first-party query/page metrics and live buyer-specific coverage without assuming a current storm"
            ),
        })
    result.sort(key=lambda r: (-r["priority_points_for_research_only"], r["state"]))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "generated_at": now.isoformat(),
        "fresh_for_research": True,
        "geo_source_fresh": geo_fresh, "coverage_source_fresh": coverage_fresh,
        "geo_source_observed_at": latest_geo.isoformat(),
        "coverage_source_observed_at": latest_coverage.isoformat(),
        "coverage_source_sha256": coverage.get("source_hash"),
        "unmapped_coverage_zip_rows": unmapped_coverage_rows,
        "state_count": len(result),
        "states": result,
        "active_roofing_alert_count": sum(len(v) for v in by_state.values()),
        "matching_alert_states": sum(bool(v) for v in by_state.values()),
        "scope": "US_STATE_LEVEL_RESEARCH_ONLY",
        "no_alert_implies_no_storm": False,
        "buyer_geo_verified": False,
        "human_lead_verified": False, "property_damage_verified": False,
        "market_gap_or_competitor_rank_measured": False,
        "market_demand_estimated": False,
        "site_traffic_or_call_revenue_verified": False,
        "outbound_authorized": False, "paid_traffic_authorized": False,
        "call_traffic_authorized": False, "execution_authority": "none",
    }


def refresh(repo_root: Path) -> dict:
    payload = build_geo_research(
        geo=json.loads((repo_root / GEO).read_text(encoding="utf-8")),
        coverage=json.loads((repo_root / COVERAGE).read_text(encoding="utf-8")),
    )
    dst = repo_root / DEST
    if not dst.parent.is_dir() or dst.parent.is_symlink() or dst.is_symlink():
        raise ValueError("unsafe original competitive runtime path")
    fd, tmp = tempfile.mkstemp(prefix=".call-geo-", dir=dst.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(payload, writer, indent=2, sort_keys=True)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root)
    payload = refresh(root) if args.refresh else build_geo_research(
        geo=json.loads((root / GEO).read_text(encoding="utf-8")),
        coverage=json.loads((root / COVERAGE).read_text(encoding="utf-8")),
    )
    print(json.dumps({
        "status": "STATE_LEVEL_CALL_RESEARCH_RECONCILED",
        "fresh": payload["fresh_for_research"],
        "alert_count": payload["active_roofing_alert_count"],
        "candidate_state_count": payload["state_count"],
        "ranked_states": [x["state"] for x in payload["states"]],
        "buyer_accepted_geography_count": 0,
        "homeowner_leads_inferred": 0,
        "outbound_authorized": False,
        "wrote_original_runtime": args.refresh,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
