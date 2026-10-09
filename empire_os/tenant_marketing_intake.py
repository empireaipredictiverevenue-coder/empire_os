"""Explicit tenant authorization boundary for Marketing Agency planning.

This contract permits a tenant-scoped Opportunity Radar candidate to enter
Marketing Agency planning. It grants no external execution authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping


SCHEMA_VERSION = "empire.tenant_marketing_intake.v1"
PURPOSE = "marketing_agency_planning"
MAX_AUTHORIZATION_AGE_SECONDS = 86400
FUTURE_CLOCK_SKEW_SECONDS = 60


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_timestamp(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def build_tenant_marketing_intake(
    *,
    tenant_id: str,
    opportunity_key: str,
    evidence_refs: list[str],
    authorized_at: str,
) -> dict[str, Any]:
    tenant = _clean(tenant_id)
    key = _clean(opportunity_key)
    timestamp = _clean(authorized_at)

    refs = list(dict.fromkeys(
        _clean(value)
        for value in evidence_refs
        if _clean(value)
    ))

    if not tenant:
        raise ValueError("tenant_id required")
    if not key:
        raise ValueError("opportunity_key required")
    if not refs:
        raise ValueError("authorization evidence required")
    if not timestamp:
        raise ValueError("authorized_at required")

    intake_id = "tenant_marketing_" + sha256(
        f"{tenant}|{key}|{PURPOSE}".encode()
    ).hexdigest()[:24]

    return {
        "schema_version": SCHEMA_VERSION,
        "intake_id": intake_id,
        "tenant_id": tenant,
        "opportunity_key": key,
        "purpose": PURPOSE,
        "authorized_at": timestamp,
        "evidence_refs": refs,
        "planning_authorized": True,

        # This boundary grants planning only.
        "execution_authority": "none",
        "outreach_authority": "none",
        "traffic_authority": "none",
        "call_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }


def tenant_marketing_intake_matches(
    intake: Mapping[str, Any] | None,
    *,
    tenant_id: str,
    opportunity_key: str,
    now: datetime,
    max_age_seconds: int = MAX_AUTHORIZATION_AGE_SECONDS,
) -> bool:
    if not isinstance(intake, Mapping):
        return False

    if intake.get("schema_version") != SCHEMA_VERSION:
        return False
    if intake.get("purpose") != PURPOSE:
        return False
    if intake.get("planning_authorized") is not True:
        return False

    if _clean(intake.get("tenant_id")) != _clean(tenant_id):
        return False
    if _clean(intake.get("opportunity_key")) != _clean(opportunity_key):
        return False

    if now.tzinfo is None or max_age_seconds <= 0:
        return False

    authorized_at = _parse_timestamp(intake.get("authorized_at"))
    if authorized_at is None:
        return False

    age_seconds = (
        now.astimezone(timezone.utc) - authorized_at
    ).total_seconds()
    if age_seconds < -FUTURE_CLOCK_SKEW_SECONDS:
        return False
    if age_seconds > max_age_seconds:
        return False

    refs = intake.get("evidence_refs")
    if not isinstance(refs, list) or not any(_clean(v) for v in refs):
        return False

    # Hostile authority expansion invalidates the intake.
    for field in (
        "execution_authority",
        "outreach_authority",
        "traffic_authority",
        "call_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        if intake.get(field) != "none":
            return False

    return True
