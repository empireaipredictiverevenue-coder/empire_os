"""Evidence-first commercial Opportunity Decay assessment.

This module determines whether explicit opportunity timing evidence is active,
stale, expired, or unknown. It never modifies Predictive Revenue inputs or
grants execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


HARD_WINDOW_FIELDS: tuple[str, ...] = (
    "source_expires_at",
    "buyer_need_until",
    "capacity_until",
)


def _parse_time(value: Any, field: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _refs(row: Mapping[str, Any]) -> tuple[str, ...]:
    raw = row.get("evidence_refs") or ()
    if not isinstance(raw, (list, tuple, set)):
        return ()
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in raw
            if str(value).strip()
        )
    )


@dataclass(frozen=True)
class OpportunityDecayAssessment:
    opportunity_key: str
    state: str
    as_of: str
    last_validated_at: str | None
    expired_fields: tuple[str, ...]
    stale_by_seconds: int | None
    recency_factor_candidate: float | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    recommendation_only: bool = True
    prediction_only: bool = True
    actual_revenue: bool = False
    buyer_intent_inferred: bool = False
    allocation_authorized: bool = False
    outreach_authorized: bool = False
    payment_authorized: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_opportunity_decay(
    evidence: Mapping[str, Any] | None,
    *,
    as_of: datetime | None = None,
) -> OpportunityDecayAssessment:
    row = dict(evidence or {})
    key = str(row.get("opportunity_key") or "").strip()
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    refs = _refs(row)
    blockers: list[str] = []

    if not key:
        blockers.append("opportunity_key_missing")

    observed = _parse_time(row.get("observed_at"), "observed_at")
    revalidated = _parse_time(
        row.get("revalidated_at"),
        "revalidated_at",
    )
    last_validated = revalidated or observed

    deadlines: dict[str, datetime] = {}
    for field in HARD_WINDOW_FIELDS:
        value = _parse_time(row.get(field), field)
        if value is not None:
            deadlines[field] = value

    expired = tuple(
        field
        for field, deadline in deadlines.items()
        if deadline <= now
    )

    freshness_seconds = row.get("freshness_window_seconds")
    freshness: int | None
    if freshness_seconds is None:
        freshness = None
    else:
        try:
            freshness = int(freshness_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "freshness_window_seconds must be an integer"
            ) from exc
        if freshness <= 0:
            raise ValueError(
                "freshness_window_seconds must be positive"
            )

    stale_by: int | None = None
    if freshness is not None:
        if last_validated is None:
            blockers.append("validation_timestamp_missing")
        else:
            stale_threshold = last_validated + timedelta(
                seconds=freshness
            )
            if stale_threshold < now:
                stale_by = int((now - stale_threshold).total_seconds())

    has_temporal_contract = bool(deadlines) or freshness is not None
    if not has_temporal_contract:
        blockers.append("temporal_validity_contract_missing")
    if not refs:
        blockers.append("evidence_refs_missing")

    if expired:
        state = "EXPIRED"
        factor: float | None = 0.0
    elif stale_by is not None:
        state = "STALE"
        factor = None
    elif (
        refs
        and has_temporal_contract
        and (freshness is None or last_validated is not None)
    ):
        state = "ACTIVE"
        factor = 1.0
    else:
        state = "UNKNOWN"
        factor = None

    if not refs and state != "UNKNOWN":
        state = "UNKNOWN"
        factor = None

    return OpportunityDecayAssessment(
        opportunity_key=key,
        state=state,
        as_of=now.isoformat(),
        last_validated_at=(
            last_validated.isoformat()
            if last_validated is not None
            else None
        ),
        expired_fields=expired,
        stale_by_seconds=stale_by,
        recency_factor_candidate=factor,
        evidence_refs=refs,
        blockers=tuple(dict.fromkeys(blockers)),
    )
