"""Phase 8 canonical Revenue CRM read-model foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RevenueCrmProspect:
    prospect_id: str
    business_name: str | None
    niche: str | None
    metro: str | None
    prospect_status: str | None
    conversation_id: str | None
    conversation_channel: str | None
    conversation_state: str | None
    closer_case_id: str | None
    closer_state: str | None
    fulfilment_order_id: str | None
    fulfilment_state: str | None
    price_cents: int | None
    deal_probability: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_revenue_crm_prospect(
    row: Mapping[str, Any],
) -> RevenueCrmProspect:
    prospect_id = str(row.get("prospect_id") or "").strip()
    if not prospect_id:
        raise ValueError("canonical prospect_id required")
    probability = row.get("deal_probability")
    if probability is not None:
        probability = float(probability)
        if probability < 0 or probability > 1:
            raise ValueError("deal_probability must be between 0 and 1")
    return RevenueCrmProspect(
        prospect_id=prospect_id,
        business_name=row.get("business_name"),
        niche=row.get("niche"),
        metro=row.get("metro"),
        prospect_status=row.get("prospect_status"),
        conversation_id=row.get("conversation_id"),
        conversation_channel=row.get("conversation_channel"),
        conversation_state=row.get("conversation_state"),
        closer_case_id=row.get("closer_case_id"),
        closer_state=row.get("closer_state"),
        fulfilment_order_id=row.get("fulfilment_order_id"),
        fulfilment_state=row.get("fulfilment_state"),
        price_cents=(
            int(row["price_cents"])
            if row.get("price_cents") is not None
            else None
        ),
        deal_probability=probability,
    )


@dataclass(frozen=True)
class RevenueCrmBuyer:
    buyer_id: str
    buyer_name: str | None
    niche: str | None
    metro: str | None
    commercial_activation_state: str | None
    daily_cap: int | None
    calls_today: int | None
    available_capacity: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def normalise_revenue_crm_buyer(
    row: Mapping[str, Any],
) -> RevenueCrmBuyer:
    buyer_id = str(row.get("buyer_id") or row.get("id") or "").strip()
    if not buyer_id:
        raise ValueError("canonical buyer_id required")

    daily_cap = (
        int(row["daily_cap"])
        if row.get("daily_cap") is not None
        else None
    )
    calls_today = (
        int(row["calls_today"])
        if row.get("calls_today") is not None
        else None
    )
    available = None
    if daily_cap is not None and calls_today is not None:
        available = max(daily_cap - calls_today, 0)

    return RevenueCrmBuyer(
        buyer_id=buyer_id,
        buyer_name=row.get("buyer_name"),
        niche=row.get("niche"),
        metro=row.get("metro"),
        commercial_activation_state=row.get(
            "commercial_activation_state"
        ),
        daily_cap=daily_cap,
        calls_today=calls_today,
        available_capacity=available,
    )
