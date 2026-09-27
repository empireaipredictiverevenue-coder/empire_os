"""Phase 9 advertising observation freshness and creative economics review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from empire_os.advertising_brain import AdPerformanceObservation


@dataclass(frozen=True)
class AdObservationFreshness:
    creative_id: str | None
    observed_at: str
    age_seconds: float
    freshness: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CreativeEconomicsReview:
    creative_id: str
    observation_count: int
    total_spend_cents: int
    total_conversions: int | None
    total_attributed_revenue_cents: int | None
    total_attributed_gross_profit_cents: int | None
    roas: float | None
    profit_roas: float | None
    attribution_complete: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdvertisingEvidenceReview:
    campaign_id: str
    observation_count: int
    fresh_for_review: bool
    creative_comparison_available: bool
    freshness: tuple[AdObservationFreshness, ...]
    creatives: tuple[CreativeEconomicsReview, ...]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    campaign_creation: bool = False
    budget_mutation: bool = False
    pause_mutation: bool = False
    retarget_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "freshness": [row.as_dict() for row in self.freshness],
            "creatives": [row.as_dict() for row in self.creatives],
        }


def _parse_timestamp(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("observed_at is required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    return parsed.astimezone(timezone.utc)


def _creative_economics(
    creative_id: str,
    rows: Sequence[AdPerformanceObservation],
) -> CreativeEconomicsReview:
    spend = sum(row.spend_cents for row in rows)
    conversions_known = all(row.conversions is not None for row in rows)
    revenue_known = all(
        row.attributed_revenue_cents is not None for row in rows
    )
    profit_known = all(
        row.attributed_gross_profit_cents is not None for row in rows
    )
    conversions = (
        sum(int(row.conversions or 0) for row in rows)
        if rows and conversions_known
        else None
    )
    revenue = (
        sum(int(row.attributed_revenue_cents or 0) for row in rows)
        if rows and revenue_known
        else None
    )
    profit = (
        sum(int(row.attributed_gross_profit_cents or 0) for row in rows)
        if rows and profit_known
        else None
    )
    roas = revenue / spend if spend > 0 and revenue is not None else None
    profit_roas = profit / spend if spend > 0 and profit is not None else None
    return CreativeEconomicsReview(
        creative_id=creative_id,
        observation_count=len(rows),
        total_spend_cents=spend,
        total_conversions=conversions,
        total_attributed_revenue_cents=revenue,
        total_attributed_gross_profit_cents=profit,
        roas=round(roas, 4) if roas is not None else None,
        profit_roas=(
            round(profit_roas, 4) if profit_roas is not None else None
        ),
        attribution_complete=bool(rows) and revenue_known and profit_known,
    )


def review_advertising_evidence(
    observations: Sequence[AdPerformanceObservation],
    *,
    campaign_id: str,
    now: datetime,
    max_age_seconds: int = 21600,
) -> AdvertisingEvidenceReview:
    cid = str(campaign_id or "").strip()
    if not cid:
        raise ValueError("campaign_id required")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    rows = tuple(observations)
    if any(row.campaign_id != cid for row in rows):
        raise ValueError("advertising evidence contains mixed campaign ids")

    current = now.astimezone(timezone.utc)
    blockers: list[str] = []
    freshness_rows: list[AdObservationFreshness] = []
    if not rows:
        blockers.append("campaign_observations_missing")

    for index, row in enumerate(rows):
        observed = _parse_timestamp(row.observed_at)
        age = (current - observed).total_seconds()
        status = "fresh"
        if age < -60:
            status = "future"
            blockers.append(f"observation_{index}_evidence_from_future")
        elif age > max_age_seconds:
            status = "stale"
            blockers.append(f"observation_{index}_evidence_stale")
        freshness_rows.append(AdObservationFreshness(
            creative_id=row.creative_id,
            observed_at=row.observed_at,
            age_seconds=round(age, 3),
            freshness=status,
        ))

    grouped: dict[str, list[AdPerformanceObservation]] = {}
    missing_creative = False
    for row in rows:
        creative_id = str(row.creative_id or "").strip()
        if not creative_id:
            missing_creative = True
            continue
        grouped.setdefault(creative_id, []).append(row)
    if missing_creative:
        blockers.append("creative_identity_missing")

    creative_reviews = tuple(
        _creative_economics(key, tuple(grouped[key]))
        for key in sorted(grouped)
    )
    for review in creative_reviews:
        if not review.attribution_complete:
            blockers.append(
                f"creative_{review.creative_id}_attribution_incomplete"
            )

    freshness_blocked = any(
        row.freshness != "fresh" for row in freshness_rows
    )
    fresh_for_review = bool(rows) and not freshness_blocked
    creative_comparison_available = (
        len(creative_reviews) >= 2
        and all(row.attribution_complete for row in creative_reviews)
        and not missing_creative
    )

    return AdvertisingEvidenceReview(
        campaign_id=cid,
        observation_count=len(rows),
        fresh_for_review=fresh_for_review,
        creative_comparison_available=creative_comparison_available,
        freshness=tuple(freshness_rows),
        creatives=creative_reviews,
        blockers=tuple(sorted(set(blockers))),
    )
