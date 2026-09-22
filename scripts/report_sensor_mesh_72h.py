#!/usr/bin/env python3
"""Founder-facing snapshot of the active EmpireOS discovery sensor mesh.

Read-only aggregation only. It does not start sensors, create prospects,
send outreach, place calls, move funds, or grant execution authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/srv/empire_os")
CRAWLER_LOG = ROOT / "runtime/crawler_72h/crawler_runs.jsonl"
COMMUNITY = ROOT / "runtime/community_intent/latest.json"
MARKET_GPS = ROOT / "runtime/market_sweeps/revenue_gps_latest.json"
REVENUE_PULSE = ROOT / "runtime/revenue_pulse/latest.json"
COMPETITOR = (
    ROOT
    / "runtime/competitive_intelligence/competitor_audience_latest.json"
)


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _crawler() -> dict[str, Any]:
    counts = Counter()
    source_events = Counter()
    unique_signals: set[str] = set()
    created: set[str] = set()
    matched: set[str] = set()

    try:
        lines = CRAWLER_LOG.read_text(errors="ignore").splitlines()
    except OSError:
        lines = []

    for raw in lines:
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = str(row.get("msg") or "")
        source = str(row.get("source") or "")
        if source:
            source_events[source] += 1

        if msg == "crawler_run_start":
            counts["runs_started"] += 1
        elif msg == "crawler_run_done":
            counts["runs_completed"] += 1
        elif msg == "source_run_done":
            counts["source_runs_completed"] += 1
            counts["candidates_seen"] += int(row.get("candidates") or 0)
            counts["accepted_total"] += int(row.get("accepted") or 0)
            counts["errors_total"] += int(row.get("errors") or 0)
        elif msg == "signal_queued":
            sid = str(row.get("signal_id") or "")
            if sid:
                unique_signals.add(sid)
        elif msg == "prospect_acquired":
            pid = str(row.get("prospect_id") or "")
            if pid:
                created.add(pid)
        elif msg == "prospect_matched":
            pid = str(row.get("prospect_id") or "")
            if pid:
                matched.add(pid)
        elif msg == "candidate_quality_rejected":
            counts["quality_rejections"] += 1
        elif msg == "canonical_identity_ambiguous":
            counts["identity_ambiguous"] += 1
        elif msg in {"canonical_ingest_failed", "source_crashed"}:
            counts["failures"] += 1

    return {
        "active_trial": CRAWLER_LOG.exists(),
        "runs_started": counts["runs_started"],
        "runs_completed": counts["runs_completed"],
        "source_runs_completed": counts["source_runs_completed"],
        "candidates_seen": counts["candidates_seen"],
        "accepted_total": counts["accepted_total"],
        "unique_signals": len(unique_signals),
        "unique_prospects_created": len(created),
        "unique_prospects_matched": len(matched),
        "quality_rejections": counts["quality_rejections"],
        "identity_ambiguous": counts["identity_ambiguous"],
        "failures": counts["failures"],
        "source_event_counts": dict(source_events.most_common()),
    }


def _community(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"available": False}
    return {
        "available": True,
        "observed_at": data.get("observed_at"),
        "mode": data.get("mode"),
        "observations": data.get("observations"),
        "new_observations": data.get("new_observations"),
        "high_intent": data.get("high_intent"),
        "medium_intent": data.get("medium_intent"),
        "by_source": data.get("by_source"),
        "pain_points": data.get("pain_points"),
        "source_status": data.get("source_status"),
        "execution_authority": data.get("execution_authority"),
    }


def _market(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"available": False}
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "market_count": data.get("market_count"),
        "commercial_demand_market_count": (
            data.get("commercial_demand_market_count")
        ),
        "competitive_evidence_market_count": (
            data.get("competitive_evidence_market_count")
        ),
        "research_queue_count": len(data.get("research_queue") or []),
        "top_research_markets": (data.get("research_queue") or [])[:5],
        "execution_authority": data.get("execution_authority"),
    }


def _pulse(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"available": False}
    revenue = data.get("recognized_revenue_truth") or {}
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "pulse_state": data.get("pulse_state"),
        "highest_priority_blocker": data.get("highest_priority_blocker"),
        "recognized_revenue_cents": revenue.get(
            "recognized_revenue_cents"
        ),
        "realized_gp_cents": revenue.get("realized_gp_cents"),
        "storm": data.get("storm"),
    }


def _competitor(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"available": False}
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "latest_observed_at": data.get("latest_observed_at"),
        "company_count": data.get("company_count"),
        "competitor_count": data.get("competitor_count"),
        "unique_evidence_count": data.get("unique_evidence_count"),
        "stacked_company_count": data.get("stacked_company_count"),
        "execution_authority": data.get("execution_authority"),
    }


def main() -> int:
    payload = {
        "schema_version": "empire.sensor_mesh_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "none",
        "crawler_72h": _crawler(),
        "community_intent": _community(_json(COMMUNITY)),
        "market_gps": _market(_json(MARKET_GPS)),
        "revenue_pulse": _pulse(_json(REVENUE_PULSE)),
        "competitor_audience": _competitor(_json(COMPETITOR)),
        "outreach_sent_by_report": False,
        "live_calls_placed_by_report": False,
        "payment_actions_by_report": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
