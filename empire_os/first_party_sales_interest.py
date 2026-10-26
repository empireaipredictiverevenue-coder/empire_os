"""First-party founder-led sales interest, reusing EmpireDB prospect ingestion.

This is a commercial enquiry intake, NOT a second CRM, payment system,
checkout, email sender, or autonomous closer. All offers remain nonbinding.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.sb import request_json
from empire_os.organic_campaign_touch import normalize_organic_touch
from empire_os.digital_avatar_approved_catalog_preview import (
    APPROVAL_REF as AVATAR_PRICE_APPROVAL_REF,
    has_recorded_price_only_founder_approval,
)
from empire_os.digital_avatar_pricing_economics_proposal import (
    DIGITAL_AVATAR_PRICING_PROPOSALS,
)
from empire_os.digital_avatar_commercial_packaging import (
    get_avatar_commercial_package,
)

SOURCE_URL = "https://empire-ai.co.uk/commercial"
SCHEMA = "empire.first-party-commercial-interest.v1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_:.-]{7,127}$")
# Browser-stated first-party entry point only. A URL or UTM query must never
# become verified SEO attribution, a trusted referrer, or marketing consent.
# Reuse existing published routes, not a duplicate tracking database.
REVIEWED_ENTRY_PATHS = frozenset({
    "/",
    "/commercial",
    "/predictive-revenue",
    "/industries/roofing",
    "/industries/solar",
    "/industries/hvac",
    "/industries/property",
    "/insights/revenue-opportunity-assessment",
    # Only the original three founder-approved, published AEO guides.
    # Entry remains browser-claimed and never implies SEO attribution.
    "/aeo/general_contractor/NYC/",
    "/aeo/hvac/DFW/",
    "/aeo/roofing/DFW/",
})


def _claimed_entry_path(value: Any) -> str | None:
    """A bounded *unverified* website path; no URL, query, IDs or PII."""
    if value is None:
        return None
    if not isinstance(value, str) or value not in REVIEWED_ENTRY_PATHS:
        raise CommercialInterestError("invalid_claimed_entry_page")
    return value

# Existing founder decision for these *consultancy* offers, not a claim that
# EmpireDB catalog versions or fulfilment terms are already verified.
CONSULTANCY = (
    ("consultancy_opportunity_assessment", "Opportunity Assessment",
     250000, "GBP", "one_time", "2026-10-11:founder-consultancy-prices"),
    ("consultancy_strategy_blueprint", "Strategy Blueprint",
     750000, "GBP", "one_time", "2026-10-11:founder-consultancy-prices"),
    ("consultancy_strategic_advisory", "Strategic Advisory",
     300000, "GBP", "monthly", "2026-10-11:founder-consultancy-prices"),
)
Request = Callable[..., Any]


class CommercialInterestError(ValueError):
    """Invalid or currently unavailable commercial enquiry."""


def _text(value: Any, label: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise CommercialInterestError("invalid_" + label)
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > limit or any(ord(x) < 32 for x in normalized):
        raise CommercialInterestError("invalid_" + label)
    return normalized


def _email(value: Any) -> str:
    normalized = _text(value, "email", limit=320).lower()
    if not EMAIL_RE.fullmatch(normalized):
        raise CommercialInterestError("invalid_email")
    return normalized


def _domain(value: Any) -> str:
    domain = _text(value, "domain", limit=253).lower()
    domain = domain.removeprefix("https://").removeprefix("http://")
    domain = domain.split("/", 1)[0].split(":", 1)[0].strip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise CommercialInterestError("invalid_company_domain")
    return domain


def founder_led_commercial_offers(
    *, root: str | Path = "/srv/empire_os",
) -> dict[str, Any]:
    """Only previously approved prices; no implied capacity or binding terms."""
    offers: list[dict[str, Any]] = []
    for code, name, price, currency, interval, approval in CONSULTANCY:
        offers.append({
            "product_code": code,
            "name": name,
            "offer_family": "consultancy",
            "currency": currency,
            "approved_price_cents": price,
            "price_interval": interval,
            "founder_price_approval_reference": approval,
            "delivery_scope_verified": False,
            "binding_terms_ready": False,
            "checkout_enabled": False,
            "fulfilment_automated": False,
            "sale_mode": "FOUNDER_LED_PROPOSAL_ONLY",
        })
    if has_recorded_price_only_founder_approval(root):
        for policy in DIGITAL_AVATAR_PRICING_PROPOSALS:
            package = get_avatar_commercial_package(policy.package_key)
            offers.append({
                "product_code": policy.product_code,
                "name": package.product_name,
                "offer_family": "digital_avatar",
                "currency": "USD",
                "approved_price_cents": policy.monthly_price_cents,
                "price_interval": "monthly",
                "founder_price_approval_reference": AVATAR_PRICE_APPROVAL_REF,
                "implementation_fee_cents": policy.implementation_fee_cents,
                "included_active_avatars": policy.included_active_avatars,
                "included_verified_meetings_per_month": policy.included_verified_meetings_per_month,
                "proposed_concurrency_entitlement": policy.proposed_concurrency_entitlement,
                "delivery_scope_verified": False,
                "binding_terms_ready": False,
                "checkout_enabled": False,
                "fulfilment_automated": False,
                "sale_mode": "FOUNDER_LED_PROPOSAL_ONLY",
            })
    # The existing verified one-time catalog can also accept a manual
    # proposal enquiry when binding order creation remains independently OFF.
    # Never invent product status or serve stale/unknown price data.
    from empire_os.self_serve_checkout import SELF_SERVE_PRODUCT_CODES
    catalog_path = Path(root) / "runtime/commercial_catalog/latest.json"
    try:
        if catalog_path.is_symlink() or catalog_path.stat().st_size > 2_000_000:
            raise ValueError("catalog_untrusted")
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(
            str(data.get("generated_at")).replace("Z", "+00:00")
        )
        age = datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)
        if (data.get("schema_version") != "empire.commercial-product-catalog.v1"
                or data.get("execution_authority") != "none"
                or data.get("actual_revenue") is not False
                or not isinstance(data.get("products"), list)
                or type(data.get("product_count")) is not int
                or data["product_count"] != len(data["products"])
                or age.total_seconds() < -120
                or age.total_seconds() > 1200):
            raise ValueError("catalog_not_fresh_verified")
        seen: set[str] = set()
        for item in data["products"]:
            if not isinstance(item, Mapping):
                raise ValueError("catalog_row_untrusted")
            code = item.get("product_code")
            if code not in SELF_SERVE_PRODUCT_CODES:
                continue
            if code in seen:
                raise ValueError("duplicate_verified_intelligence_product")
            seen.add(code)
            basis = item.get("price_basis")
            if (item.get("active") is not True
                    or item.get("binding_terms_ready") is not True
                    or item.get("catalog_state") != "VERIFIED"
                    or item.get("version_state") != "VERIFIED"
                    or item.get("billing_model") != "one_time"
                    or not isinstance(basis, Mapping)
                    or basis.get("state") != "VERIFIED"
                    or basis.get("currency") != "USD"
                    or type(basis.get("amount_cents")) is not int
                    or not 1 <= basis["amount_cents"] <= 29900):
                continue
            offers.append({
                "product_code": code,
                "name": str(item.get("product_name") or code)[:200],
                "offer_family": "intelligence_product",
                "currency": "USD",
                "approved_price_cents": basis["amount_cents"],
                "price_interval": "one_time",
                "founder_price_approval_reference": "verified_catalog:" + code,
                "delivery_scope_verified": True,
                "binding_terms_ready": False,  # not within *this* enquiry path
                "checkout_enabled": False,
                "fulfilment_automated": False,
                "sale_mode": "FOUNDER_LED_PROPOSAL_ONLY",
            })
    except (OSError, ValueError, TypeError, OverflowError):
        # Base founder-approved consultation/Avatar enquiries remain possible.
        pass
    return {
        "schema_version": SCHEMA,
        "status": "FOUNDER_LED_ENQUIRY_AVAILABLE",
        "count": len(offers),
        "offers": offers,
        "scope": "BUYER_INITIATED_CONTACT_ONLY",
        "outbound_authority": "none",
        "payment_authority": "none",
        "commercial_terms_binding": False,
        "checkout_authorized": False,
        "actual_revenue": False,
    }


def record_founder_led_interest(
    *,
    product_code: str,
    business_name: str,
    email: str,
    domain: str,
    industry: str,
    geography: str,
    desired_outcome: str,
    contact_consent: bool,
    idempotency_key: str,
    website: str = "",
    organic_touch: Mapping[str, str] | None = None,
    claimed_entry_page: str | None = None,
    source_campaign_key: str | None = None,
    source_landing_url: str | None = None,
    root: str | Path = "/srv/empire_os",
    request: Request = request_json,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write one buyer-stated prospect with explicit response consent; no send."""
    if contact_consent is not True:
        raise CommercialInterestError("specific_contact_consent_required")
    if website:
        raise CommercialInterestError("invalid_submission")
    try:
        validated_touch = normalize_organic_touch(organic_touch) if organic_touch is not None else None
    except ValueError as exc:
        raise CommercialInterestError("invalid_organic_campaign_touch") from exc
    code = _text(product_code, "product_code", limit=120)
    catalog = founder_led_commercial_offers(root=root)
    offer = next((o for o in catalog["offers"] if o["product_code"] == code), None)
    if offer is None:
        raise CommercialInterestError("offer_not_approved_for_enquiry")

    business = _text(business_name, "business_name", limit=200)
    address = _email(email)
    host = _domain(domain)
    sector = _text(industry, "industry", limit=120)
    market = _text(geography, "geography", limit=160)
    outcome = _text(desired_outcome, "desired_outcome", limit=1200)
    entry_page = _claimed_entry_path(claimed_entry_page)
    key = _text(idempotency_key, "idempotency_key", limit=128)
    if not KEY_RE.fullmatch(key):
        raise CommercialInterestError("invalid_idempotency_key")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise CommercialInterestError("contact_consent_clock_untrusted")

    # NewsJack URL tags remain explicitly unverified buyer claims.
    if validated_touch is not None and (source_campaign_key is not None or source_landing_url is not None):
        raise CommercialInterestError("conflicting_campaign_source_claims")
    # Registered YouTube source is checked independently and cannot co-exist with JEV.
    from empire_os.youtube_commercial_source_bridge import review_commercial_video_source_submission
    try:
        campaign_source = review_commercial_video_source_submission(
            source_campaign_key=source_campaign_key,
            source_landing_url=source_landing_url,
            registry_root=Path(root),
            now=moment,
        )
    except ValueError as exc:
        raise CommercialInterestError("commercial_youtube_source_unverified") from exc

    digest = hashlib.sha256(address.encode("utf-8")).hexdigest()[:24]
    capture_key = hashlib.sha256(
        f"{code}|{host}|{key}".encode("utf-8")
    ).hexdigest()
    consent_evidence = {
        "kind": "buyer_initiated_specific_response_consent",
        "observed_at": moment.astimezone(timezone.utc).isoformat(),
        "consent_to_contact": True,
        "newsletter_or_ongoing_marketing_consent": False,
        "source_url": SOURCE_URL,
    }
    evidence = {
        "source": "first_party_commercial_sales_enquiry",
        "buyer_stated": True,
        "requested_product_code": code,
        "offer_family": offer["offer_family"],
        "approved_price_cents": offer["approved_price_cents"],
        "approved_price_currency": offer["currency"],
        "approved_price_interval": offer["price_interval"],
        "price_approval_reference": offer["founder_price_approval_reference"],
        "contact_email": address,
        "company_domain": host,
        "industry": sector,
        "geography": market,
        "desired_outcome": outcome,
        "contact_consent_evidence": consent_evidence,
        "automatic_followup_authorized": False,
        "outreach_authority": "none",
        "binding_terms_ready": False,
        "checkout_authorized": False,
        "delivery_scope_verified": False,
        "costs_or_capacity_verified": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    # A visitor/browser-submitted path is useful for funnel *review*, but
    # does not prove a search visit, a payable event, or ongoing consent.
    # Legacy direct enquiries stay identical: never fabricate a source.
    if entry_page is not None:
        evidence["claimed_entry_page_review"] = {
            "path": entry_page,
            "source": "UNVERIFIED_BROWSER_SUBMITTED",
            "organic_search_attributed": False,
            "search_click_proven": False,
            "qualified_buyer_proven": False,
            "marketing_consent_granted": False,
            "recognized_revenue_proven": False,
        }
    if campaign_source is not None:
        evidence["youtube_buyer_declared_source"] = campaign_source["source_evidence"]
    if validated_touch is not None:
        evidence["organic_campaign_touch"] = validated_touch
    result = request(
        "POST",
        "/rest/v1/rpc/ingest_prospect_atomic",
        payload={
            "p_prospect": {
                "business_name": business,
                "niche": "commercial_sales:" + offer["offer_family"],
                "metro": market,
                "buy_signal_score": 0,
                "contact_source": "first_party_commercial_sales_enquiry",
                "contacted_status": "not_contacted",
            },
            "p_evidence": evidence,
            "p_ingest_key": "commercial-sales:" + capture_key,
            "p_identity_keys": ["domain:" + host, "email:" + digest],
        },
    )
    if not isinstance(result, Mapping):
        raise CommercialInterestError("commercial_intake_unavailable")
    decision = result.get("decision")
    if decision not in {"created", "existing_ingest", "existing_identity"}:
        raise CommercialInterestError("commercial_intake_not_recorded")
    prospect = result.get("prospect")
    if not isinstance(prospect, Mapping) or not str(prospect.get("id") or ""):
        raise CommercialInterestError("commercial_intake_identity_not_confirmed")
    return {
        "schema_version": SCHEMA,
        "decision": "commercial_enquiry_recorded",
        "product_code": code,
        "offer_family": offer["offer_family"],
        "reference": capture_key[:20],
        "next_step": "FOUNDER_REVIEW",
        "automated_contact_sent": False,
        "binding_commercial_terms": False,
        "checkout_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
