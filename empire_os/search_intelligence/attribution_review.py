"""Phase 5 evidence-only search attribution chronology and profit review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .attribution import (
    SearchRevenueAttributionPreview,
    preview_search_revenue_attribution,
)


@dataclass(frozen=True)
class SearchAttributionReview:
    revenue: SearchRevenueAttributionPreview
    search_touch_observed_at: str
    attribution_lag_seconds: float | None
    revenue_attribution_ready: bool
    profit_attribution_ready: bool
    observed_cost_cents: int | None
    realized_gross_profit_cents: int | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    write_authority: str = "none"
    publishing_execution: bool = False
    indexation_execution: bool = False
    revenue_mutation: bool = False
    accounting_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["revenue"] = self.revenue.as_dict()
        return data


def _parse(value: str, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def review_search_attribution(
    *,
    site_id: str,
    commercial_event: Mapping[str, Any],
    search_touch_observed_at: str,
    touch_evidence_ref: str,
    page_id: str | None = None,
    query: str | None = None,
    external_session_id: str | None = None,
    prospect_id: str | None = None,
    opportunity_id: str | None = None,
    attribution_kind: str = "observed_search_touch",
    observed_cost_cents: int | None = None,
    cost_evidence_ref: str | None = None,
    max_attribution_lag_seconds: int = 2592000,
) -> SearchAttributionReview:
    if max_attribution_lag_seconds <= 0:
        raise ValueError("max_attribution_lag_seconds must be positive")
    if observed_cost_cents is not None and observed_cost_cents < 0:
        raise ValueError("observed_cost_cents must be nonnegative")

    revenue = preview_search_revenue_attribution(
        site_id=site_id,
        commercial_event=commercial_event,
        page_id=page_id,
        query=query,
        external_session_id=external_session_id,
        prospect_id=prospect_id,
        opportunity_id=opportunity_id,
        attribution_kind=attribution_kind,
    )

    touch_ref = str(touch_evidence_ref or "").strip()
    if not touch_ref:
        raise ValueError("search touch evidence reference required")

    touch_time = _parse(
        search_touch_observed_at,
        label="search_touch_observed_at",
    )
    revenue_time = _parse(revenue.occurred_at, label="revenue_occurred_at")

    blockers: list[str] = []
    lag = (revenue_time - touch_time).total_seconds()
    if lag < 0:
        blockers.append("revenue_precedes_search_touch")
    elif lag > max_attribution_lag_seconds:
        blockers.append("search_touch_outside_attribution_window")

    refs = [touch_ref, f"commercial_event:{revenue.commercial_event_id}"]
    realized_gp = None
    cost_ref = str(cost_evidence_ref or "").strip()
    if observed_cost_cents is not None:
        if not cost_ref:
            blockers.append("observed_cost_evidence_reference_missing")
        else:
            refs.append(cost_ref)
            realized_gp = revenue.revenue_cents - observed_cost_cents
    elif cost_ref:
        blockers.append("observed_cost_value_missing")

    revenue_blockers = tuple(
        blocker
        for blocker in blockers
        if blocker
        in {
            "revenue_precedes_search_touch",
            "search_touch_outside_attribution_window",
        }
    )
    profit_blockers = list(revenue_blockers)
    if observed_cost_cents is None or not cost_ref:
        profit_blockers.append("observed_cost_evidence_missing")

    return SearchAttributionReview(
        revenue=revenue,
        search_touch_observed_at=touch_time.isoformat(),
        attribution_lag_seconds=round(lag, 3) if lag >= 0 else None,
        revenue_attribution_ready=not revenue_blockers,
        profit_attribution_ready=not tuple(sorted(set(profit_blockers))),
        observed_cost_cents=observed_cost_cents,
        realized_gross_profit_cents=(
            realized_gp
            if not revenue_blockers and cost_ref and observed_cost_cents is not None
            else None
        ),
        blockers=tuple(sorted(set(blockers + profit_blockers))),
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
