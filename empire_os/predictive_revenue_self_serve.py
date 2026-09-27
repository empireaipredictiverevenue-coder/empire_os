"""Public-interest intake for Predictive Revenue deployments.

This records buyer-stated enterprise interest into the canonical prospect
acquisition path. It does not infer company size, accept binding commercial
terms, authorize outreach, create a payment request, deploy infrastructure, or
recognize revenue.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Mapping

from empire_os.predictive_revenue_products import predictive_revenue_product
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
REVENUE_BANDS = frozenset({
    "unknown",
    "under_1m",
    "1m_5m",
    "5m_25m",
    "25m_100m",
    "100m_500m",
    "500m_plus",
})


class PredictiveRevenueInterestError(RuntimeError):
    pass


def _text(value: Any, label: str, max_length: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > max_length:
        raise PredictiveRevenueInterestError(f"invalid {label}")
    return text


def _domain(value: Any) -> str:
    text = _text(value, "domain", 253).lower()
    text = (
        text.removeprefix("https://")
        .removeprefix("http://")
        .split("/", 1)[0]
        .split(":", 1)[0]
        .strip(".")
    )
    if not DOMAIN_RE.fullmatch(text):
        raise PredictiveRevenueInterestError("invalid domain")
    return text


def _email(value: Any) -> str:
    text = _text(value, "email", 320).lower()
    if not EMAIL_RE.fullmatch(text):
        raise PredictiveRevenueInterestError("invalid email")
    return text


def _identity_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def record_predictive_revenue_interest(
    *,
    product_code: str,
    business_name: str,
    email: str,
    domain: str,
    industry: str,
    geography: str,
    annual_revenue_band: str,
    desired_outcome: str,
    systems: list[str] | tuple[str, ...],
    idempotency_key: str,
    request: Request = request_json,
) -> dict[str, Any]:
    product = predictive_revenue_product(product_code)
    business = _text(business_name, "business_name", 200)
    contact_email = _email(email)
    company_domain = _domain(domain)
    vertical = _text(industry, "industry", 120)
    market = _text(geography, "geography", 160)
    outcome = _text(desired_outcome, "desired_outcome", 1200)
    key = _text(idempotency_key, "idempotency_key", 128)

    band = str(annual_revenue_band or "unknown").strip().lower()
    if band not in REVENUE_BANDS:
        raise PredictiveRevenueInterestError("invalid annual_revenue_band")

    normalized_systems = []
    for value in systems or []:
        item = " ".join(str(value or "").strip().split())
        if item and len(item) <= 80 and item not in normalized_systems:
            normalized_systems.append(item)
    if len(normalized_systems) > 20:
        raise PredictiveRevenueInterestError("too many systems")

    evidence = {
        "source": "self_serve_predictive_revenue",
        "source_url": "https://empire-ai.co.uk/predictive-revenue",
        "buyer_stated": True,
        "contact_email": contact_email,
        "company_domain": company_domain,
        "requested_product_code": product.product_code,
        "approved_entry_price_cents": product.deployment_price_cents,
        "price_type": product.price_type,
        "pricing_state": product.pricing_state,
        "annual_revenue_band": band,
        "industry": vertical,
        "geography": market,
        "desired_outcome": outcome,
        "systems": normalized_systems,
        "binding_commercial_terms": False,
        "deployment_scope_verified": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }

    ingest_key = "predictive-revenue:" + key
    identity_keys = [
        "domain:" + company_domain,
        "email:" + _identity_hash(contact_email),
    ]
    result = request(
        "POST",
        "/rest/v1/rpc/ingest_prospect_atomic",
        payload={
            "p_prospect": {
                "business_name": business,
                "niche": "predictive_revenue:" + vertical.lower(),
                "metro": market,
                "buy_signal_score": 0,
                "contact_source": "self_serve_predictive_revenue",
                "contacted_status": "not_contacted",
            },
            "p_evidence": evidence,
            "p_ingest_key": ingest_key,
            "p_identity_keys": identity_keys,
        },
    ) or {}

    if not isinstance(result, Mapping):
        raise PredictiveRevenueInterestError("predictive revenue intake failed")
    decision = str(result.get("decision") or "")
    if decision not in {"created", "existing_ingest", "existing_identity"}:
        raise PredictiveRevenueInterestError(
            f"predictive revenue intake unavailable:{decision or 'unknown'}"
        )
    prospect = result.get("prospect")
    prospect_id = (
        str(prospect.get("id") or "")
        if isinstance(prospect, Mapping)
        else ""
    )
    if not prospect_id:
        raise PredictiveRevenueInterestError("prospect id missing")

    return {
        "decision": "deployment_interest_recorded",
        "prospect_id": prospect_id,
        "source_decision": decision,
        "product_code": product.product_code,
        "product_name": product.name,
        "approved_entry_price_cents": product.deployment_price_cents,
        "price_type": product.price_type,
        "binding_commercial_terms": False,
        "deployment_scope_verified": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
