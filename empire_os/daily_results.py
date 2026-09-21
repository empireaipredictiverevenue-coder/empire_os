"""Canonical daily operating-results projection for EmpireOS."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from empire_os.control_conveyor import build_conveyor

LONDON = ZoneInfo("Europe/London")
_INT = re.compile(r"(?<![\d.])(\d[\d,]*)")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _job_counts(repo_root: Path) -> dict[str, int]:
    base = repo_root / "runtime" / "coder" / "jobs"
    return {
        status: len(list((base / status).glob("*.json")))
        if (base / status).exists()
        else 0
        for status in ("pending", "running", "completed", "failed")
    }


def _stage_rows(loop: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (loop.get("stages") or [])
        if isinstance(row, Mapping)
    ]


def _stage_map(loop: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("stage") or ""): row
        for row in _stage_rows(loop)
        if str(row.get("stage") or "").strip()
    }


def _first_int(text: Any) -> int | None:
    match = _INT.search(str(text or ""))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _stage_count(stages: Mapping[str, Mapping[str, Any]], name: str) -> int | None:
    row = stages.get(name)
    if not row:
        return None
    for key in ("count", "current_count", "observed_count", "value"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return _first_int(row.get("detail"))


def build_daily_results(
    repo_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    local = current.astimezone(LONDON)
    runtime = repo_root / "runtime"

    acquisition = _read(runtime / "acquisition" / "latest.json")
    qualification = _read(runtime / "qualification" / "latest.json")
    buyer_review = _read(runtime / "buyer_review_materializer" / "latest.json")
    intent = _read(runtime / "community_intent" / "latest.json")
    loop = _read(runtime / "commercial_loop" / "latest.json")
    ops = _read(runtime / "ops_control" / "latest.json")
    source_health = _read(runtime / "source_health" / "latest.json")
    aeo = _read(runtime / "search_intelligence" / "aeo_recovery" / "latest.json")
    security = _read(runtime / "security" / "supabase_audit_latest.json")
    trust = _read(runtime / "trust" / "latest.json")
    legal_mass_tort = _read(runtime / "legal_mass_tort" / "latest.json")
    stages = _stage_map(loop)
    conveyor = (
        dict(ops.get("conveyor"))
        if isinstance(ops.get("conveyor"), Mapping)
        else build_conveyor(loop)
    )

    funnel = {
        "omega_observations": _stage_count(stages, "omega_projection"),
        "approved_buyers": _stage_count(stages, "buyer_candidate_approved"),
        "outbound_authorized": _stage_count(stages, "outbound_authorized"),
        "outbound_sent": _stage_count(stages, "outbound_sent"),
        "commercial_buyer_replies": _stage_count(stages, "buyer_conversation"),
        "verified_terms": _stage_count(stages, "commercial_terms"),
        "payment_requests": _stage_count(stages, "bsc_payment_request"),
        "verified_payments": _stage_count(stages, "bsc_usdt_payment"),
        "fulfilments": _stage_count(stages, "fulfilment"),
        "recognized_revenue_events": _stage_count(stages, "recognized_revenue"),
        "realized_gp_events": _stage_count(stages, "realized_gross_profit"),
    }

    security_findings = (
        dict(security.get("findings"))
        if isinstance(security.get("findings"), Mapping)
        else {}
    )

    return {
        "schema_version": "empire.daily_results.v1",
        "date": local.date().isoformat(),
        "generated_at": current.isoformat(),
        "timezone": "Europe/London",
        "truth_policy": {
            "unknown_stays_unknown": True,
            "forecast_is_not_actual": True,
            "send_is_not_revenue": True,
            "payment_request_is_not_payment": True,
        },
        "headline": {
            "technical_health": ops.get("healthy"),
            "commercial_blocker": conveyor.get("current_blocker"),
            "blocker_owner": conveyor.get("owner_component"),
            "blocker_authority": conveyor.get("authority"),
            "recognized_revenue_events": funnel["recognized_revenue_events"],
            "realized_gp_events": funnel["realized_gp_events"],
        },
        "commercial_funnel": funnel,
        "acquisition": {
            "source": acquisition.get("source"),
            "metro": acquisition.get("metro"),
            "accepted": acquisition.get("accepted"),
            "quality_accepted": acquisition.get("quality_accepted"),
            "quality_rejected": acquisition.get("quality_rejected"),
            "errors": acquisition.get("errors"),
            "observed_at": acquisition.get("observed_at"),
            "source_healthy": source_health.get("end_to_end_healthy"),
        },
        "qualification": {
            "qualified": qualification.get("qualified"),
            "processed": qualification.get("processed"),
            "written": qualification.get("written"),
            "errors": qualification.get("errors"),
            "observed_at": qualification.get("observed_at"),
        },
        "buyer_review": {
            "scanned": buyer_review.get("scanned"),
            "eligible": buyer_review.get("eligible"),
            "probed": buyer_review.get("probed"),
            "proposed": buyer_review.get("proposed"),
            "review_ready": buyer_review.get("review_ready"),
            "deferred_enrichment": buyer_review.get("deferred_enrichment"),
            "rejection_reasons": buyer_review.get("rejection_reasons"),
            "errors": buyer_review.get("errors"),
        },
        "intent_and_pain": {
            "observations": intent.get("observations"),
            "new_observations": intent.get("new_observations"),
            "high_intent": intent.get("high_intent"),
            "medium_intent": intent.get("medium_intent"),
            "by_source": intent.get("by_source"),
            "source_status": intent.get("source_status"),
            "pain_points": intent.get("pain_points"),
            "opportunity_routes": len(intent.get("control_fabric_routes") or []),
        },
        "search_and_seo": {
            "aeo_asset_count": aeo.get("asset_count"),
            "aeo_status_counts": aeo.get("status_counts"),
            "aeo_risk_counts": aeo.get("risk_counts"),
            "timesfm_shadow_enabled": False,
            "traffic_forecast_mode": "SHADOW_COMPARE",
        },
        "legal_intelligence": {
            "market": legal_mass_tort.get("market"),
            "source_count_ready": legal_mass_tort.get("source_count_ready"),
            "source_count_total": legal_mass_tort.get("source_count_total"),
            "firm_buyer_intelligence": legal_mass_tort.get("firm_buyer_intelligence"),
            "consumer_targeting": legal_mass_tort.get("consumer_targeting"),
            "live_market_evidence_bound": legal_mass_tort.get("live_market_evidence_bound"),
            "market_opportunities_observed": legal_mass_tort.get("market_opportunities_observed"),
        },
        "deal_room": {
            "provider": "documenso",
            "bridge_ready": (repo_root / "empire_os/deal_room.py").exists(),
            "provider_execution_activated": False,
            "binding_acceptance": False,
            "payment_request_created": False,
            "revenue_recognition": False,
        },
        "coder": _job_counts(repo_root),
        "reliability": {
            "healthy": ops.get("healthy"),
            "incident_count": (
                (ops.get("incident_manager") or {}).get("incident_count")
                if isinstance(ops.get("incident_manager"), Mapping)
                else None
            ),
            "safe_repairs_queued": len(
                (ops.get("sentinel") or {}).get("repair_plan") or []
            )
            if isinstance(ops.get("sentinel"), Mapping)
            else None,
            "current_blocker": conveyor.get("current_blocker"),
            "conveyor": conveyor,
        },
        "security": {
            "supabase_audit_available": bool(security),
            "findings": security_findings,
            "trust_snapshot_available": bool(trust),
            "trust_ready": (
                (trust.get("assessment") or {}).get("public_trust_center_ready")
                if isinstance(trust.get("assessment"), Mapping)
                else None
            ),
        },
        "commercial_stages": _stage_rows(loop),
        "execution_authority": "none",
        "controls_execution": False,
    }
