"""Tenant-bound, aggregate-only CRM source adapter for PRIME.

Authenticates through the *existing* restricted PostgresRevenueCrmRepository.
Do not install another CRM DB role or transform prospects into deals.
Caller must construct that repository via the existing signed tenant/membership
authority, not from an arbitrary tenant string supplied to a public endpoint.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)

READ_LIMIT = 100


class PrimeCrmReadUnavailable(RuntimeError):
    """CRM evidence cannot be asserted. No credential or data included."""


def review_authenticated_crm_prospects(
    *, repository: PostgresRevenueCrmRepository, tenant_id: str,
    limit: int = READ_LIMIT,
) -> dict[str, Any]:
    if type(repository) is not PostgresRevenueCrmRepository:
        raise PrimeCrmReadUnavailable("existing dedicated Revenue CRM repository required")
    try:
        tenant = str(UUID(tenant_id))
    except (TypeError, ValueError, AttributeError):
        raise PrimeCrmReadUnavailable("canonical CRM tenant identity required") from None
    if tenant != repository.tenant_id or tenant != tenant_id:
        raise PrimeCrmReadUnavailable("CRM tenant mismatch")
    if type(limit) is not int or not 1 <= limit <= READ_LIMIT:
        raise PrimeCrmReadUnavailable("bounded CRM source view required")
    try:
        rows = repository.prospects(limit=limit)
    except RevenueCrmTransportError:
        raise PrimeCrmReadUnavailable("canonical CRM read unavailable") from None
    if type(rows) is not list or len(rows) > limit:
        raise PrimeCrmReadUnavailable("invalid CRM source limit")
    seen = set()
    metrics = {
        "returned_prospect_rows": len(rows),
        "engaged_conversation_rows": 0,
        "proposal_ready_rows": 0,
        "awaiting_payment_rows": 0,
        "priced_closer_rows": 0,
        "probability_field_present_rows": 0,
    }
    for row in rows:
        if not isinstance(row, dict) or str(row.get("tenant_id")) != tenant:
            raise PrimeCrmReadUnavailable("CRM source row tenant mismatch")
        try:
            record_id = str(UUID(str(row.get("prospect_id"))))
        except (TypeError, ValueError, AttributeError):
            raise PrimeCrmReadUnavailable("invalid CRM prospect identity") from None
        if record_id in seen:
            raise PrimeCrmReadUnavailable("duplicate CRM prospect identity")
        seen.add(record_id)
        if row.get("conversation_id") is not None and str(row.get("conversation_state") or "").lower() == "engaged":
            metrics["engaged_conversation_rows"] += 1
        closer = row.get("closer_case_id") is not None
        if closer and str(row.get("closer_state") or "").lower() == "proposal_ready":
            metrics["proposal_ready_rows"] += 1
        if closer and str(row.get("closer_state") or "").lower() == "awaiting_payment":
            metrics["awaiting_payment_rows"] += 1
        price = row.get("price_cents")
        if price is not None:
            if type(price) not in (int, Decimal) or not Decimal(price).is_finite():
                raise PrimeCrmReadUnavailable("invalid CRM price projection")
            if Decimal(price) < 0 or Decimal(price) != Decimal(price).to_integral_value():
                raise PrimeCrmReadUnavailable("invalid CRM price projection")
            if closer and Decimal(price) > 0:
                metrics["priced_closer_rows"] += 1
        probability = row.get("deal_probability")
        if probability is not None:
            try:
                prob = Decimal(str(probability))
            except (ValueError, ArithmeticError):
                raise PrimeCrmReadUnavailable("invalid CRM probability projection") from None
            if not prob.is_finite() or not 0 <= prob <= 1:
                raise PrimeCrmReadUnavailable("invalid CRM probability projection")
            metrics["probability_field_present_rows"] += 1

    return {
        "schema_version": "empire.predictive_revenue.prime_crm_read.v1",
        "mode": "OBSERVE",
        "source_status": "AUTHENTICATED_TENANT_CRM_VIEW_READ",
        **metrics,
        "source_view_limit": limit,
        "source_exhaustive": False,
        "prospects_are_not_verified_deals": True,
        "prospect_probability_is_not_independently_calibrated": True,
        "source_payment_events_not_read": True,
        "modelled_pipeline_forecast_cents": None,
        "recognized_revenue_cents": None,
        "executed_outbound": False,
        "execution_authority": "none",
    }
