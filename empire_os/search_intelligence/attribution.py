"""Evidence-only search-to-revenue attribution preview."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SearchRevenueAttributionPreview:
    site_id: str
    page_id: str | None
    query: str | None
    external_session_id: str | None
    prospect_id: str | None
    opportunity_id: str | None
    fulfilment_order_id: str
    commercial_event_id: str
    revenue_cents: int
    attribution_kind: str
    occurred_at: str
    actual_revenue: bool = True
    write_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_search_revenue_attribution(
    *,
    site_id: str,
    commercial_event: Mapping[str, Any],
    page_id: str | None = None,
    query: str | None = None,
    external_session_id: str | None = None,
    prospect_id: str | None = None,
    opportunity_id: str | None = None,
    attribution_kind: str = "observed_search_touch",
) -> SearchRevenueAttributionPreview:
    site = str(site_id or "").strip()
    if not site:
        raise ValueError("site_id required")
    if not isinstance(commercial_event, Mapping):
        raise ValueError("commercial_event must be a mapping")

    event_type = str(commercial_event.get("event_type") or "").strip()
    actual = commercial_event.get("actual_revenue") is True
    event_id = str(commercial_event.get("id") or "").strip()
    order_id = str(
        commercial_event.get("fulfilment_order_id") or ""
    ).strip()
    occurred_at = str(commercial_event.get("occurred_at") or "").strip()

    if event_type != "revenue_recognized" or not actual:
        raise ValueError("commercial event is not recognized actual revenue")
    if not event_id or not order_id or not occurred_at:
        raise ValueError("recognized revenue evidence identity is incomplete")

    amount = commercial_event.get("amount_cents")
    if amount is None:
        raise ValueError("recognized revenue amount is required")
    revenue_cents = int(amount)
    if revenue_cents < 0:
        raise ValueError("recognized revenue amount must be nonnegative")

    page = str(page_id).strip() if page_id is not None else None
    normalized_query = str(query).strip() if query is not None else None
    session = (
        str(external_session_id).strip()
        if external_session_id is not None
        else None
    )
    if not page and not normalized_query and not session:
        raise ValueError(
            "attribution requires observed page, query, or session evidence"
        )

    kind = str(attribution_kind or "").strip()
    if not kind:
        raise ValueError("attribution_kind required")

    return SearchRevenueAttributionPreview(
        site_id=site,
        page_id=page or None,
        query=normalized_query or None,
        external_session_id=session or None,
        prospect_id=(
            str(prospect_id).strip() if prospect_id is not None else None
        ),
        opportunity_id=(
            str(opportunity_id).strip()
            if opportunity_id is not None
            else None
        ),
        fulfilment_order_id=order_id,
        commercial_event_id=event_id,
        revenue_cents=revenue_cents,
        attribution_kind=kind,
        occurred_at=occurred_at,
    )
