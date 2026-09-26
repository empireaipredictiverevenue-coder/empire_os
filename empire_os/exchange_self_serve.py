"""Self-serve Lead Exchange buyer interest capture.

Buyer-stated tier, territory and capacity are captured as demand evidence only.
This module never activates a buyer seat, verifies capacity, accepts commercial
terms, sends leads, creates a payment request or recognizes revenue.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from empire_os.phase4_exchange_mrr_products import (
    EXCHANGE_MRR_PRODUCTS,
    public_exchange_seat_projection,
)
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
ALLOWED_DELIVERY = frozenset({"email", "webhook", "api", "phone"})
TIER_CODES = frozenset(row.product_code for row in EXCHANGE_MRR_PRODUCTS)


class ExchangeInterestError(RuntimeError):
    pass


def _text(value: Any, label: str, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_length:
        raise ExchangeInterestError(f"invalid {label}")
    return text


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def exchange_tier_catalog() -> dict[str, Any]:
    return public_exchange_seat_projection()


def record_exchange_interest(
    *,
    tier_code: str,
    business_name: str,
    email: str,
    domain: str,
    niche: str,
    territory: str,
    daily_capacity: int,
    delivery_preference: str,
    exclusivity_interest: bool = False,
    request: Request = request_json,
) -> dict[str, Any]:
    tier = _text(tier_code, "tier_code", 100).lower()
    if tier not in TIER_CODES:
        raise ExchangeInterestError("unsupported exchange tier")

    business = _text(business_name, "business_name", 200)
    contact_email = _text(email, "email", 320).lower()
    if not EMAIL_RE.fullmatch(contact_email):
        raise ExchangeInterestError("invalid email")

    buyer_domain = _text(domain, "domain", 253).lower()
    buyer_domain = (
        buyer_domain.removeprefix("https://")
        .removeprefix("http://")
        .split("/", 1)[0]
        .split(":", 1)[0]
        .strip(".")
    )
    if not DOMAIN_RE.fullmatch(buyer_domain):
        raise ExchangeInterestError("invalid domain")

    vertical = _text(niche, "niche", 120)
    market = _text(territory, "territory", 160)
    if type(daily_capacity) is not int or daily_capacity < 1 or daily_capacity > 10000:
        raise ExchangeInterestError("daily_capacity must be between 1 and 10000")

    delivery = _text(
        delivery_preference,
        "delivery_preference",
        40,
    ).lower()
    if delivery not in ALLOWED_DELIVERY:
        raise ExchangeInterestError("unsupported delivery preference")

    tier_row = next(
        row for row in EXCHANGE_MRR_PRODUCTS
        if row.product_code == tier
    )
    if (
        exclusivity_interest is True
        and tier_row.exclusivity_eligible is not True
    ):
        raise ExchangeInterestError(
            "selected tier is not eligible for exclusivity"
        )

    corridor_key = (
        "requested:"
        + _slug(vertical)
        + ":"
        + _slug(market)
    )
    stated = {
        "source": "self_serve_exchange_interest",
        "buyer_stated": True,
        "email": contact_email,
        "requested_tier": tier,
        "niche": vertical,
        "territory": market,
        "requested_corridor_key": corridor_key,
        "daily_capacity": daily_capacity,
        "delivery_preference": delivery,
        "exclusivity_interest": bool(exclusivity_interest),
        "capacity_verified": False,
        "commercial_terms_verified": False,
        "pricing_binding": False,
        "actual_revenue": False,
    }

    result = request(
        "POST",
        "/rest/v1/rpc/propose_buyer_scout_candidate",
        payload={
            "p_domain": buyer_domain,
            "p_business_name": business,
            "p_website": f"https://{buyer_domain}",
            "p_description": (
                f"Buyer-stated Lead Exchange interest for {vertical} "
                f"in {market}; requested {daily_capacity}/day via {delivery}."
            ),
            "p_buyer_type": "self_serve_exchange_interest",
            "p_direct_buyer_score": 0,
            "p_explicit_direct_buyer_evidence": False,
            "p_target_buyer_pools": ["commercial_exchange"],
            "p_target_product_codes": [tier],
            "p_target_corridor_keys": [corridor_key],
            "p_query_evidence": [stated],
            "p_site_evidence": {},
            "p_provenance": {
                "source": "empire-ai.co.uk/buy",
                "intake": "self_serve_exchange_interest_v1",
                "buyer_stated": True,
                "requested_tier": tier,
                "requested_daily_capacity": daily_capacity,
                "requested_delivery_preference": delivery,
                "requested_exclusivity": bool(exclusivity_interest),
                "pricing_binding": False,
                "outreach_authorized": False,
                "actual_revenue": False,
            },
            "p_actor": "self-serve-exchange-interest",
        },
    ) or {}

    if not isinstance(result, Mapping):
        raise ExchangeInterestError("exchange intake returned invalid result")
    if str(result.get("decision") or "") != "candidate_recorded":
        raise ExchangeInterestError("exchange intake was not recorded")

    return {
        "decision": "interest_recorded",
        "candidate_id": result.get("candidate_id"),
        "tier_code": tier,
        "requested_corridor_key": corridor_key,
        "daily_capacity": daily_capacity,
        "delivery_preference": delivery,
        "exclusivity_interest": bool(exclusivity_interest),
        "pricing_binding": False,
        "seat_activated": False,
        "capacity_verified": False,
        "commercial_terms_verified": False,
        "outreach_authorized": False,
        "actual_revenue": False,
    }
