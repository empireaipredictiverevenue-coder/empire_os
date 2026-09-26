"""Build a non-binding, company-route outreach draft from a permit buyer packet.

This module drafts only. It does not send, mutate buyer state, accept terms,
request payment, allocate inventory, or recognize revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import re


OUTPUT_DIR = Path("runtime/revenue/permit_buyer_outreach")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _format_money(amount_cents: Any, currency: Any) -> str:
    try:
        cents = int(amount_cents)
    except (TypeError, ValueError):
        raise ValueError("verified offer amount required")
    if cents <= 0:
        raise ValueError("verified offer amount required")
    code = _text(currency).upper()
    if code != "USD":
        raise ValueError("permit buyer outreach currently requires USD")
    return "$" + f"{cents / 100:,.0f}"


def build_permit_buyer_outreach_draft(
    packet: Mapping[str, Any],
    *,
    founder_name: str = "Phil",
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if packet.get("conversation_ready") is not True:
        raise ValueError("conversation-ready commercial packet required")
    if packet.get("live_outbound_send") is not False:
        raise ValueError("packet must not already authorize outbound")

    buyer = dict(packet.get("buyer") or {})
    supply = dict(packet.get("supply") or {})
    offer = dict(packet.get("offer") or {})
    routes = dict(packet.get("contact_routes") or {})

    business = _text(buyer.get("business_name"))
    domain = _text(buyer.get("domain"))
    if not business or not domain:
        raise ValueError("buyer identity required")

    emails = [
        _text(value).lower()
        for value in (routes.get("emails") or [])
        if _text(value)
    ]
    if not emails:
        raise ValueError("company email route required")
    if routes.get("person_bound") is not False:
        raise ValueError("this draft is specifically for company-route outreach")

    decision_makers = [
        dict(row)
        for row in (packet.get("decision_makers") or [])
        if isinstance(row, Mapping)
    ]
    named = [
        _text(row.get("name"))
        for row in decision_makers
        if _text(row.get("name"))
    ]
    attention = " or ".join(named[:2]) if named else business + " team"

    verified_count = int(supply.get("verified_current_inventory") or 0)
    if verified_count <= 0:
        raise ValueError("verified permit supply required")

    product = _text(offer.get("product_name")) or "Permit Intelligence"
    price = _format_money(offer.get("amount_cents"), offer.get("currency"))
    unit = _text(offer.get("unit"))
    if unit != "per_month":
        raise ValueError("verified monthly offer basis required")

    subject = "NYC permit intelligence for VIP Fire Sprinklers"
    body = (
        f"Hi {business} team — attention {attention},\n\n"
        "I’m reaching out because your first-party site shows active NYC "
        "coverage, and we’re currently validating a live NYC permit/project-"
        "start intelligence feed.\n\n"
        f"So far, {verified_count:,} NYC permit records have passed current-"
        "source revalidation. I’m not assuming all of those are relevant to "
        "fire-sprinkler work—the useful version for you would be filtered to "
        "the project/permit types and boroughs you actually want to see.\n\n"
        f"Our current verified catalog basis for {product} is {price}/month. "
        "Before I suggest any commercial terms, I’d rather confirm fit. Could "
        "you reply with:\n"
        "• the NYC boroughs / project types you want\n"
        "• roughly how many opportunities you could review per day or week\n"
        "• whether you prefer email or webhook delivery\n"
        f"• whether {price}/month is in the right range if the feed is useful\n\n"
        "If easier, just send the coverage area and capacity and I’ll map the "
        "current verified feed against it.\n\n"
        f"Best,\n{founder_name}\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        "31 St Thomas St, Bolton, BL1 2QR, UK\n"
        "If you’d rather not hear from me, reply “opt out”."
    )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    return {
        "schema_version": "empire.permit-buyer-outreach-draft.v1",
        "mode": "DRAFT_REVIEW_ONLY",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "buyer_domain": domain,
        "business_name": business,
        "recipient_route": {
            "email": emails[0],
            "route_type": "company_route",
            "person_bound": False,
            "attention": attention,
        },
        "subject": subject,
        "body_text": body,
        "capacity_intake_fields": [
            "territory",
            "project_or_permit_types",
            "daily_or_weekly_capacity",
            "delivery_route",
            "price_range_fit",
        ],
        "reply_parsers": [
            "buyer_capacity_intake_v1",
            "buyer_stated_price_v1",
        ],
        "evidence_rules": {
            "verified_supply_count_is_total_current_nyc_supply": True,
            "verified_supply_count_is_not_claimed_as_fire_sprinkler_fit": True,
            "catalog_price_is_verified": True,
            "person_bound_recipient_claimed": False,
        },
        "send_gate_ready": False,
        "send_gate_blockers": [
            "founder_live_outbound_approval_required",
            "company_route_not_person_bound",
        ],
        "live_outbound_send": False,
        "buyer_activation_performed": False,
        "terms_accepted": False,
        "payment_request_created": False,
        "actual_revenue": False,
        "execution_authority": "draft_only",
    }


def write_permit_buyer_outreach_draft(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    domain = re.sub(
        r"[^a-z0-9.-]+",
        "_",
        _text(payload.get("buyer_domain")).lower(),
    )
    if not domain:
        raise ValueError("buyer domain required")
    path = root / OUTPUT_DIR / f"{domain}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
