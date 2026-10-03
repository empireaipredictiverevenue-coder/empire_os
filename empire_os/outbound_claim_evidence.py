"""Claim-to-evidence binding for governed outbound copy.

Every prospect-specific claim can be checked against a supplied evidence index before the
Outbound Governor allows the message to progress. This module never creates claims,
changes evidence, or authorizes sending.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


_SENSITIVE_CLAIM_KINDS = {
    "pricing",
    "performance_outcome",
    "guarantee",
    "scarcity",
    "relationship",
    "urgency",
    "revenue",
}

_ALLOWED_SOURCE_KINDS = {
    "official_site",
    "official_site_current",
    "public_record",
    "press_release",
    "canonical_product",
    "canonical_commercial_evidence",
    "buyer_stated",
    "provider_event",
}


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_claim_evidence(
    claims: Iterable[Mapping[str, Any]],
    evidence_index: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    claim_rows = [dict(row) for row in claims]
    evidence_rows = {
        str(key): dict(value)
        for key, value in dict(evidence_index or {}).items()
        if isinstance(value, Mapping)
    }

    hard_holds: list[str] = []
    evidence_holds: list[str] = []
    resolved: list[dict[str, Any]] = []

    for index, claim in enumerate(claim_rows):
        text = str(claim.get("text") or claim.get("claim") or "").strip()
        claim_kind = str(claim.get("kind") or "observed_fact").strip().lower()
        evidence_ref = str(claim.get("evidence_ref") or "").strip()

        claim_result = {
            "index": index,
            "text": text,
            "kind": claim_kind,
            "evidence_ref": evidence_ref or None,
            "status": "UNKNOWN",
        }

        if not text:
            hard_holds.append("claim_text_missing")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue

        if not evidence_ref:
            hard_holds.append("claim_evidence_ref_missing")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue

        evidence = evidence_rows.get(evidence_ref)
        if evidence is None:
            hard_holds.append("claim_evidence_ref_unresolved")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue

        if evidence.get("verified") is not True:
            evidence_holds.append("claim_evidence_unverified")
            claim_result["status"] = "ESCALATE"
            resolved.append(claim_result)
            continue

        source_kind = str(evidence.get("source_kind") or "").strip().lower()
        if source_kind not in _ALLOWED_SOURCE_KINDS:
            evidence_holds.append("claim_evidence_source_not_approved")
            claim_result["status"] = "ESCALATE"
            resolved.append(claim_result)
            continue

        expires_at = _parse_ts(evidence.get("expires_at"))
        if evidence.get("expires_at") is not None and expires_at is None:
            hard_holds.append("claim_evidence_expiry_invalid")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue
        if expires_at is not None and expires_at <= timestamp:
            hard_holds.append("claim_evidence_expired")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue

        if (
            claim_kind in _SENSITIVE_CLAIM_KINDS
            and evidence.get("canonical") is not True
        ):
            hard_holds.append("sensitive_claim_requires_canonical_evidence")
            claim_result["status"] = "HOLD"
            resolved.append(claim_result)
            continue

        claim_result["status"] = "VERIFIED"
        claim_result["source_kind"] = source_kind
        resolved.append(claim_result)

    hard_holds = list(dict.fromkeys(hard_holds))
    evidence_holds = list(dict.fromkeys(evidence_holds))

    if hard_holds:
        decision = "HOLD"
    elif evidence_holds:
        decision = "ESCALATE"
    else:
        decision = "VERIFIED"

    return {
        "decision": decision,
        "claims_checked": len(claim_rows),
        "claims": resolved,
        "hard_holds": hard_holds,
        "evidence_holds": evidence_holds,
        "mutation_authorized": False,
        "send_authorized": False,
    }
