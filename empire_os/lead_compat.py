"""Compatibility helpers that converge legacy lead intake onto canonical prospects."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class CanonicalLeadIntakeError(RuntimeError):
    """Canonical compatibility intake failed."""


class CanonicalLeadConflict(CanonicalLeadIntakeError):
    """Canonical identity requires manual resolution."""


Ingestor = Callable[[dict[str, Any]], dict[str, Any]]


def normalize_lead_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    niche = str(payload.get("niche") or "").strip()
    metro = str(payload.get("metro") or "").strip()

    if not name or not niche or not metro:
        raise CanonicalLeadIntakeError(
            "name, niche and metro required"
        )

    source = str(payload.get("source") or "api").strip() or "api"
    raw = payload.get("raw")
    if not isinstance(raw, dict):
        raw = {}

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata:
        raw = {**raw, "metadata": dict(metadata)}

    external_id = str(payload.get("lead_id") or "").strip()
    if external_id:
        raw = {**raw, "external_lead_id": external_id}

    intent = str(payload.get("intent") or "").strip()
    if intent:
        raw = {**raw, "intent": intent}

    consent = str(payload.get("consent") or "").strip()
    if consent:
        raw = {**raw, "consent": consent}

    for source_key, raw_key in (
        ("zip", "zip"),
        ("ip_address", "ip_address"),
        ("user_agent", "user_agent"),
    ):
        value = str(payload.get(source_key) or "").strip()
        if value:
            raw = {**raw, raw_key: value}

    candidate = {
        "name": name,
        "niche": niche,
        "metro": metro,
        "source": source,
        "email": str(payload.get("email") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "state": str(payload.get("state") or "").strip(),
        "details": str(payload.get("details") or "").strip(),
        "url": str(payload.get("url") or "").strip(),
        "raw": raw or None,
    }

    if payload.get("lead_score") is not None:
        candidate["lead_score"] = payload.get("lead_score")

    return candidate


def canonical_lead_intake(
    payload: Mapping[str, Any],
    ingestor: Ingestor,
) -> dict[str, Any]:
    candidate = normalize_lead_payload(payload)

    try:
        result = ingestor(candidate)
    except CanonicalLeadIntakeError:
        raise
    except Exception:
        raise CanonicalLeadIntakeError(
            "canonical prospect ingest unavailable"
        ) from None

    if not isinstance(result, dict):
        raise CanonicalLeadIntakeError(
            "canonical ingest returned invalid response"
        )

    decision = str(result.get("decision") or "").strip()
    if not decision:
        raise CanonicalLeadIntakeError(
            "canonical ingest missing decision"
        )

    if decision in {"ambiguous", "conflict"}:
        raise CanonicalLeadConflict(
            "prospect identity requires manual resolution"
        )

    prospect = result.get("prospect")
    prospect_id = (
        prospect.get("id")
        if isinstance(prospect, dict)
        else result.get("prospect_id")
    )

    return {
        "ok": True,
        "decision": decision,
        "prospect_id": prospect_id,
        "niche": candidate["niche"],
        "metro": candidate["metro"],
        "status": "canonical_owned",
    }
