"""Bridge public competitor changes to original commercial review evidence.

This is a READ-ONLY interpretation of canonical sources, not buyer discovery,
CRM promotion, qualified lead attribution, or revenue recognition.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import json
import re

from empire_os.competitor_change_radar import SCHEMA as RADAR_SCHEMA, _safe_source

SCHEMA = "empire.competitor_commercial_evidence_bridge.v1"
MAX_BYTES = 3_000_000
MAX_CANDIDATES = 50
MAX_AGE = timedelta(days=7)
REQUIRED_PROOFS = (
    "buyer_acceptance", "accepted_geography", "accepted_product_criteria",
    "capacity_hours_and_caps", "written_commercial_terms",
    "qualified_conversion", "independently_verified_settlement",
)


def _time(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("timestamp is missing")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if value.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _domain(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 500:
        return ""
    value = raw.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
    except ValueError:
        return ""
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port is not None:
        return ""
    host = parsed.hostname or ""
    return host[4:] if host.startswith("www.") else host


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def build_commercial_evidence_bridge(
    radar: Mapping[str, Any],
    *,
    buyer_scout: Mapping[str, Any] | None = None,
    opportunity_briefs: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC-aware clock required")
    now = now.astimezone(timezone.utc)
    if (radar.get("schema_version") != RADAR_SCHEMA
            or radar.get("mode") != "OBSERVE"
            or radar.get("execution_authority") != "none"
            or radar.get("outreach_enabled") is not False
            or radar.get("payment_authorized") is not False
            or radar.get("buyer_intent_inferred") is not False
            or radar.get("demand_inferred") is not False
            or radar.get("verified_revenue") is not False):
        raise ValueError("radar source is not review-only")
    queue = radar.get("review_queue", [])
    baselines = radar.get("observations", [])
    if (not isinstance(queue, list) or len(queue) > 20
            or not isinstance(baselines, list) or len(baselines) > 40):
        raise ValueError("unbounded competitor observations")
    scout = buyer_scout or {}
    scout_state = "UNAVAILABLE"
    buyer_index: dict[str, dict] = {}
    if scout:
        if (scout.get("mode") != "OBSERVE"
                or scout.get("execution_authority") != "none"
                or scout.get("outbound_sent") is not False):
            raise ValueError("untrusted buyer-scouter source")
        candidates = scout.get("candidates", [])
        if not isinstance(candidates, list) or len(candidates) > 500:
            raise ValueError("unbounded buyer-scout candidates")
        scout_state = "READ_ONLY"
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            domain = _domain(candidate.get("domain", ""))
            if domain:
                # An exact web-domain match is research identity only.
                buyer_index[domain] = dict(candidate)
    briefs = opportunity_briefs or {}
    brief_state = "UNAVAILABLE"
    brief_index: dict[str, dict] = {}
    if briefs:
        if (briefs.get("mode") != "REVIEW_ONLY"
                or briefs.get("execution_authority") != "none"
                or briefs.get("external_send_allowed") is not False):
            raise ValueError("untrusted opportunity-brief source")
        items = briefs.get("briefs", [])
        if not isinstance(items, list) or len(items) > 500:
            raise ValueError("unbounded opportunity briefs")
        brief_state = "READ_ONLY"
        for brief in items:
            if isinstance(brief, Mapping):
                domain = _domain(brief.get("company_website", ""))
                if domain:
                    brief_index[domain] = dict(brief)
    observed_sites = set()
    for observation in baselines:
        if not isinstance(observation, Mapping):
            raise ValueError("untrusted baseline item")
        src = observation.get("source_ref")
        if not isinstance(src, str) or not _safe_source(src):
            raise ValueError("invalid baseline URL")
        observed_sites.add((observation.get("entity_id"), src))
    cards = []
    seen = set()
    stale_count = 0
    for item in queue:
        if not isinstance(item, Mapping):
            raise ValueError("untrusted change review")
        src = item.get("source_ref")
        if (not isinstance(src, str) or not _safe_source(src)
                or item.get("status") not in {"PENDING_REVIEW", "HUMAN_REVIEW_ONLY"}):
            raise ValueError("invalid public change evidence")
        identity = (item.get("entity_id"), src)
        if identity not in observed_sites or identity in seen:
            raise ValueError("review item has no canonical baseline or is duplicated")
        seen.add(identity)
        changes = item.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 20:
            raise ValueError("invalid change facts")
        for fact in changes:
            if (not isinstance(fact, Mapping) or fact.get("category") not in
                    {"pricing", "offers", "features", "announcements"}
                    or fact.get("change") not in {"ADDED_OR_REWORDED", "MISSING_OR_REWORDED"}
                    or not isinstance(fact.get("digest"), str)
                    or not re.fullmatch("[a-f0-9]{64}", fact["digest"])):
                raise ValueError("invalid change fact")
        last_seen = _time(item.get("latest_change_at") or item.get("observed_at"))
        if last_seen > now or now - last_seen > MAX_AGE:
            stale_count += 1
            continue
        domain = _domain(src)
        matched_buyer = buyer_index.get(domain)
        matched_brief = brief_index.get(domain)
        categories = sorted({change["category"] for change in changes})
        cards.append({
            "review_id": item.get("review_id") or None,
            "entity_id": identity[0],
            "source_ref": src,
            "observed_at": last_seen.isoformat(),
            "fact_categories": categories,
            "fact_count": len(changes),
            "fact_excerpts": [
                {"category": x["category"], "change": x["change"],
                 "text": str(x.get("text") or "")[:200]}
                for x in changes
            ],
            "evidence_level": "OBSERVED_PUBLIC_SOURCE_CHANGE_NOT_COMMERCIAL_DEMAND",
            "buyer_scout_exact_domain_match": matched_buyer is not None,
            "buyer_scout_candidate_state": (
                str(matched_buyer.get("candidate_state") or "UNKNOWN")
                if matched_buyer else None
            ),
            "buyer_scout_commercial_terms_verified": (
                matched_buyer.get("commercial_terms_verified") is True
                if matched_buyer else False
            ),
            "existing_opportunity_brief_exact_domain_match": matched_brief is not None,
            "existing_opportunity_brief_review_ready": (
                matched_brief.get("review_ready") is True if matched_brief else False
            ),
            "commercial_readiness": "REQUIRES_INDEPENDENT_QUALIFICATION",
            "required_proofs": list(REQUIRED_PROOFS),
            "next_existing_owner": "original_buyer_acquisition_research_owner",
            "recommended_next_review": (
                "Verify original public pricing or offer; separately confirm "
                "buyer role, accepted market, commercial terms and capacity."
                if any(x in {"pricing", "offers"} for x in categories)
                else "Verify original public feature change and whether an existing "
                "buyer actually requests or pays for the capability."
            ),
            "task_dispatched": False,
            "outreach_authorized": False,
            "qualified_lead": False,
            "revenue_verified": False,
        })
    cards.sort(key=lambda c: (
        not any(k in {"pricing", "offers"} for k in c["fact_categories"]),
        c["observed_at"], str(c["entity_id"]),
    ))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "radar_observed_source_count": len(observed_sites),
        "radar_pending_change_count": len(queue),
        "stale_reviews_not_actionable": stale_count,
        "current_research_brief_count": len(cards),
        "exact_buyer_scout_domain_matches": sum(
            c["buyer_scout_exact_domain_match"] for c in cards
        ),
        "exact_opportunity_brief_domain_matches": sum(
            c["existing_opportunity_brief_exact_domain_match"] for c in cards
        ),
        "buyer_scout_source_state": scout_state,
        "opportunity_brief_source_state": brief_state,
        "research_cards": cards,
        "demand_inferred": False, "buyer_admission_authorized": False,
        "buyer_acceptance_verified_from_radar": False,
        "qualified_lead_count": 0, "verified_revenue": False,
        "outreach_authorized": False, "database_writes": False,
        "execution_authority": "none",
    }


def build_bridge_runtime(repo_root: Path) -> dict[str, Any]:
    """On-demand read by existing founder feed; never materializes or fetches."""
    base = repo_root / "runtime"
    radar = _read(base / "competitive_intelligence/competitor_change_radar_latest.json")
    if not radar:
        return {"available": False, "mode": "OBSERVE", "reason": "RADAR_UNAVAILABLE",
                "current_research_brief_count": 0, "outreach_authorized": False}
    try:
        result = build_commercial_evidence_bridge(
            radar,
            buyer_scout=_read(base / "buyer_acquisition/scout_latest.json"),
            opportunity_briefs=_read(base / "opportunity_briefs/latest.json"),
        )
    except (ValueError, TypeError, KeyError):
        return {"available": False, "mode": "OBSERVE", "reason": "SOURCE_EVIDENCE_REJECTED",
                "current_research_brief_count": 0, "outreach_authorized": False}
    return {"available": True, **result}
