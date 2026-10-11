"""Claim-scoped Opportunity Evidence Resolver in shadow mode.

The resolver creates proof requirements, not normalized scores. It never
promotes public search observations into buyer intent, fulfilment or revenue.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.opportunity_commercial_source_health import (
    assess_sources, diagnostic_for_claim,
)

ROUTES = Path("runtime/opportunity_factory/evidence_routes_latest.json")
RADAR = Path("runtime/opportunity_radar/latest.json")
ATTESTATIONS = Path("runtime/opportunity_evidence/canonical_attestations_latest.json")
OUTPUT = Path("runtime/opportunity_factory/evidence_resolution_latest.json")

EVIDENCE_TYPES: dict[str, tuple[str, ...]] = {
    "buyer_intent": ("canonical_verified_reply", "canonical_rfp"),
    "demand": ("canonical_qualified_inbound", "canonical_accepted_order"),
    "urgency": ("canonical_buyer_deadline", "official_public_event"),
    "margin_potential": ("canonical_versioned_price_and_actual_cost",),
    "distribution_strength": ("canonical_approved_capacity",),
    "distribution_path": ("canonical_distribution_contract",),
    "data_advantage": ("canonical_licensed_dataset_audit",),
    "fulfilment_readiness": ("canonical_verified_capacity_and_runbook",),
    "build_complexity": ("canonical_dependency_and_test_audit",),
    "offer_key": ("canonical_active_product_version",),
    "independent_evidence": ("verified_original_record",),
    "niche": ("canonical_entity_classification",),
    "trigger": ("verified_original_event",),
}
AGE_DAYS: dict[str, int] = {
    "buyer_intent": 14, "demand": 14, "urgency": 30,
    "margin_potential": 30, "distribution_strength": 3,
    "distribution_path": 30, "data_advantage": 30,
    "fulfilment_readiness": 3, "build_complexity": 14,
    "offer_key": 30, "independent_evidence": 30,
    "niche": 90, "trigger": 30,
}
SOURCE_PREFIXES = (
    "runtime/conversations_replies_control/",
    "runtime/revenue/", "runtime/buyer_network_intelligence/",
    "runtime/commercial_exchange/", "runtime/market_sweeps/",
    "runtime/opportunity_factory/proofs/",
)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None


def claim_for(blocker: str) -> str | None:
    for suffix in ("_normalized_score_required", "_required"):
        if blocker.endswith(suffix):
            key = blocker[:-len(suffix)]
            return key if key in EVIDENCE_TYPES else None
    return None

def source_integrity(root: Path, evidence: Mapping[str, Any]) -> str:
    """Hash agreement proves byte stability, NEVER event authenticity."""
    rel = evidence.get("source_artifact")
    digest = evidence.get("source_sha256")
    if not isinstance(rel, str) or not any(
        rel.startswith(prefix) for prefix in SOURCE_PREFIXES
    ):
        return "UNTRUSTED_SOURCE_PATH"
    if not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest):
        return "SOURCE_DIGEST_REQUIRED"
    supplied = root / rel
    actual = supplied.resolve()
    if not actual.is_relative_to(root.resolve()):
        return "SOURCE_OUTSIDE_REPO"
    if supplied.is_symlink() or not actual.is_file():
        return "SOURCE_NOT_ACCESSIBLE"
    try:
        if actual.stat().st_size > 2_000_000:
            return "SOURCE_TOO_LARGE"
        if sha256(actual.read_bytes()).hexdigest() != digest:
            return "SOURCE_DIGEST_MISMATCH"
    except OSError:
        return "SOURCE_NOT_ACCESSIBLE"
    return "CONTENT_HASH_MATCH_NOT_AUTHENTICATED"


def check_candidate(
    root: Path,
    opportunity: Mapping[str, Any],
    claim: str,
    evidence: Mapping[str, Any],
    now: datetime,
) -> str:
    if claim not in EVIDENCE_TYPES:
        return "UNRECOGNIZED_CLAIM"
    if evidence.get("opportunity_key") != opportunity.get("opportunity_key"):
        return "OPPORTUNITY_BINDING_MISMATCH"
    tenant = opportunity.get("tenant_id")
    if not isinstance(tenant, str) or not tenant:
        return "OPPORTUNITY_TENANT_UNRESOLVED"
    if evidence.get("tenant_id") != tenant:
        return "TENANT_SCOPE_MISMATCH"
    if evidence.get("claim_type") != claim:
        return "CLAIM_BINDING_MISMATCH"
    if evidence.get("source_kind") not in EVIDENCE_TYPES[claim]:
        return "SOURCE_TYPE_NOT_ADMISSIBLE"
    if evidence.get("ai_generated") is not False:
        return "MODEL_ASSERTION_NOT_EVIDENCE"
    if evidence.get("verification_status") != "VERIFIED_SOURCE_EVENT":
        return "SOURCE_VERIFICATION_NOT_PROVED"
    event = _clock(evidence.get("source_event_at"))
    captured = _clock(evidence.get("captured_at"))
    if event is None or captured is None:
        return "DATED_SOURCE_REQUIRED"
    if event > now + timedelta(minutes=5) or captured > now + timedelta(minutes=5):
        return "FUTURE_DATED_SOURCE"
    if event > captured + timedelta(minutes=5):
        return "CAPTURE_BEFORE_EVENT"
    if now - event > timedelta(days=AGE_DAYS[claim]):
        return "SOURCE_STALE_FOR_CLAIM"
    status = source_integrity(root, evidence)
    if status != "CONTENT_HASH_MATCH_NOT_AUTHENTICATED":
        return status
    if not isinstance(evidence.get("source_event_id"), str) or not evidence["source_event_id"]:
        return "CANONICAL_EVENT_ID_REQUIRED"
    # A self-claimed VERIFIED_SOURCE_EVENT remains untrusted until the
    # canonical event verifier identity/authorization is independently checked.
    return "SOURCE_MATCHED_AUTHENTICITY_REVIEW_REQUIRED"


def resolve(
    root: Path,
    *,
    routes: Mapping[str, Any],
    radar: Mapping[str, Any],
    attestations: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    source_health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("offset-aware clock required")
    now = now.astimezone(timezone.utc)
    health = source_health if isinstance(source_health, Mapping) else assess_sources(root, now)
    candidates = {
        str(row["opportunity_key"]): row
        for row in (radar.get("candidates") or [])
        if isinstance(row, Mapping) and row.get("opportunity_key")
    }
    proofs = (attestations or {}).get("attestations") or []
    proofs = proofs if isinstance(proofs, list) else []
    rows = []
    reasons: Counter[str] = Counter()
    matches_needing_review = 0
    total = 0
    unscoped_opportunities = 0
    for item in routes.get("items") or []:
        if not isinstance(item, Mapping):
            continue
        key = item.get("opportunity_key")
        candidate = candidates.get(str(key)) or {"opportunity_key": key}
        tenant_bound = isinstance(candidate.get("tenant_id"), str) and bool(candidate.get("tenant_id"))
        if not tenant_bound:
            unscoped_opportunities += 1
        requirements = []
        for route in item.get("routes") or []:
            if not isinstance(route, Mapping):
                continue
            blocker = str(route.get("blocker") or "")
            claim = claim_for(blocker)
            if not claim:
                status = "UNMAPPED_BLOCKER_REQUIRES_RESEARCH"
            else:
                specific = [
                    row for row in proofs if isinstance(row, Mapping)
                    and row.get("opportunity_key") == key
                    and row.get("claim_type") == claim
                ]
                states = [
                    check_candidate(root, candidate, claim, row, now)
                    for row in specific[:10]
                ]
                if not states:
                    status = "NO_CLAIM_SPECIFIC_EVIDENCE"
                elif "SOURCE_MATCHED_AUTHENTICITY_REVIEW_REQUIRED" in states:
                    status = "SOURCE_MATCHED_AUTHENTICITY_REVIEW_REQUIRED"
                    matches_needing_review += 1
                else:
                    status = states[0]
            total += 1
            reasons[status] += 1
            requirements.append({
                "blocker": blocker,
                "claim_type": claim,
                "allowed_source_kinds": list(EVIDENCE_TYPES.get(claim, ())),
                "source_capability": route.get("capability"),
                "public_search_can_prove_commercial_claim": False,
                "evidence_state": status,
                "source_diagnostic": diagnostic_for_claim(health, claim),
                "tenant_binding_status": "TENANT_BOUND" if tenant_bound else "MISSING_TENANT_SCOPE",
                "verified_normalized_score": None,
                "next_action": (
                    "review_original_canonical_event_and_verifier"
                    if status == "SOURCE_MATCHED_AUTHENTICITY_REVIEW_REQUIRED"
                    else "obtain_claim_specific_primary_evidence"
                ),
                "execution_authority": "none",
            })
        rows.append({
            "opportunity_key": key,
            "opportunity_class": item.get("opportunity_class"),
            "requirement_count": len(requirements),
            "requirements": requirements,
            "factory_authority_changed": False,
        })
    return {
        "schema": "empire.opportunity_evidence_resolution_shadow.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "opportunities": len(rows),
        "unresolved_requirements": total,
        "source_attestations_examined": len(proofs),
        "content_hash_matches_needing_authenticity_review": matches_needing_review,
        "reason_counts": dict(sorted(reasons.items())),
        "unscoped_opportunity_count": unscoped_opportunities,
        "commercial_source_health": health,
        "items": rows,
        "normalized_scores_written": 0,
        "commercial_facts_auto_verified": 0,
        "factory_promotion_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }


def refresh(root: Path) -> dict[str, Any]:
    root = root.resolve()
    result = resolve(
        root, routes=_read(root / ROUTES), radar=_read(root / RADAR),
        attestations=_read(root / ATTESTATIONS),
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temp.replace(path)
    return result
