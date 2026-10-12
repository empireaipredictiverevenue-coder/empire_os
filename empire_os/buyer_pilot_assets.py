"""Evidence-bound buyer pilot asset generation and compliance preflight.

Creates review-only acquisition assets from an observed buyer supply policy.
It does not publish, launch campaigns, authorize traffic, set budgets, or
invent geography, payout, capacity, demand or commercial terms.
"""

from __future__ import annotations

from typing import Any, Mapping

from empire_os.buyer_supply_review import build_supply_review


SCHEMA_VERSION = "empire.buyer_pilot_assets.v1"

PROHIBITED_PATTERNS = {
    "promotions": (
        "special offer",
        "limited time",
        "sale",
        "coupon",
    ),
    "guarantees": (
        "guaranteed",
        "guarantee",
        "100% guaranteed",
    ),
    "discounts": (
        "discount",
        "save ",
        "% off",
    ),
    "unsubstantiated_claims": (
        "best",
        "#1",
        "number one",
        "lowest price",
        "cheapest",
        "instant approval",
        "same-day guaranteed",
    ),
}


def validate_asset_text(
    text: str,
    *,
    prohibited_categories: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized = str(text or "").strip().lower()
    violations: list[dict[str, str]] = []

    for category in prohibited_categories:
        for pattern in PROHIBITED_PATTERNS.get(category, ()):
            if pattern.lower() in normalized:
                violations.append(
                    {
                        "category": category,
                        "pattern": pattern,
                    }
                )

    return {
        "compliant": not violations,
        "violations": violations,
    }


def build_lead_smart_pilot_assets(
    policy: Mapping[str, Any],
    *,
    service_label: str,
) -> dict[str, Any]:
    """Create review-only generic/unbranded pilot assets."""

    review = build_supply_review(policy)

    if str(policy.get("buyer_name") or "").strip() != "Lead Smart":
        raise ValueError("Lead Smart policy required")

    service = str(service_label or "").strip()
    if not service:
        raise ValueError("service_label required")

    creative = dict(policy.get("creative") or {})
    prohibited = list(creative.get("prohibited") or [])

    landing = {
        "asset_type": "landing_page",
        "status": "draft_for_buyer_review",
        "brand": None,
        "headline": f"Looking for help with {service}?",
        "subheadline": (
            "Tell us what service you need and where the property is located."
        ),
        "body": (
            "Submit your details to request contact regarding your service need. "
            "Availability and service coverage depend on location and provider capacity."
        ),
        "cta": "Request service information",
        "claims": [],
    }

    ads = [
        {
            "asset_type": "search_ad",
            "status": "draft_for_buyer_review",
            "brand": None,
            "headline": f"{service} Service Information",
            "description": (
                f"Looking for {service}? Submit your service request and location."
            ),
        },
        {
            "asset_type": "search_ad",
            "status": "draft_for_buyer_review",
            "brand": None,
            "headline": f"Need Help With {service}?",
            "description": (
                "Provide your location and service need to request more information."
            ),
        },
    ]

    checked_assets = []

    for asset in [landing, *ads]:
        text = " ".join(
            str(value)
            for value in asset.values()
            if isinstance(value, str)
        )

        validation = validate_asset_text(
            text,
            prohibited_categories=prohibited,
        )

        checked_assets.append(
            {
                **asset,
                "compliance": validation,
            }
        )

    compliant = all(
        asset["compliance"]["compliant"]
        for asset in checked_assets
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "buyer_name": "Lead Smart",
        "source_ref": policy.get("source_ref"),
        "service_label": service,
        "mode": "REVIEW_ONLY",
        "assets": checked_assets,
        "compliance_passed": compliant,
        "buyer_asset_review_required": True,
        "traffic_source_approval_required": True,
        "buyer_approved": False,
        "published": False,
        "campaign_created": False,
        "budget_authorized": False,
        "traffic_authorized": False,
        "commercial_activation_authorized": False,
        "current_supply_review": review,
    }


# Partner-isolated, offline buyer-preview assets. Do NOT use the Lead Smart
# source template verbatim: it contains a Lead Smart-specific disclosure,
# tracking number and programme-specific qualification assumptions.
PARTNER_PREVIEW_DESCRIPTORS = {
    "inquirly.com": {
        "vertical": "Roof replacement or roof installation — buyer approval pending",
        "region": "Candidate NJ ZIPs 07001–07005 — not approved",
        "image": "roofing-hero.webp",
        "headline": "Considering a new roof?",
        "summary": "Review a homeowner-initiated roofing service enquiry concept. Coverage and approved service options are not confirmed.",
        "needs": ("Roof replacement", "New roof installation", "Roofing job eligibility"),
    },
    "leadbank": {
        "vertical": "Roofing installation or replacement",
        "region": "United States — exact ZIP coverage to be approved",
        "image": "roofing-hero.webp",
        "headline": "Need help with a roofing replacement?",
        "summary": "Describe the roofing project and property location. Service options depend on independently confirmed provider coverage.",
        "needs": ("Roof replacement", "New roof installation", "Storm-damaged roofing"),
    },
    "validated": {
        "vertical": "Roofing installation or replacement",
        "region": "United States — exact ZIP coverage to be approved",
        "image": "roofing-hero.webp",
        "headline": "Exploring a roof replacement?",
        "summary": "Share what work is needed and where the home is located. Availability depends on the buyer-approved market and service capacity.",
        "needs": ("Roof replacement", "Roof installation", "Damage assessment enquiry"),
    },
    "connexis": {
        "vertical": "Home services — first buyer programme unselected",
        "region": "UK or US — buyer market and postcode/ZIP to be confirmed",
        "image": None,
        "headline": "Looking for help with a home service?",
        "summary": "Tell us about the property and type of work. Available services and locations have not yet been confirmed.",
        "needs": ("Property repair enquiry", "Home improvement project", "Service-area eligibility"),
    },
}


def build_partner_landing_review(pilot: Mapping[str, Any]) -> dict[str, Any]:
    """Produce zero-authority buyer review copy using an existing pilot packet.

    The input must come from the private existing partner readiness registry.
    This does not create a public page or capture customer information.
    """
    if not isinstance(pilot, Mapping):
        raise ValueError("partner_pilot_required")
    key = pilot.get("entity_key")
    if key not in PARTNER_PREVIEW_DESCRIPTORS:
        raise ValueError("unknown_partner_preview")
    packet = pilot.get("technical_review_packet")
    if not isinstance(packet, Mapping) or packet.get("entity_key") != key:
        raise ValueError("partner_packet_binding_mismatch")
    if packet.get("lead_smart_route_or_number_inherited") is not False:
        raise ValueError("partner_route_must_be_isolated")
    if packet.get("traffic_enabled") is not False or packet.get("execution_authority") != "NONE":
        raise ValueError("review_requires_zero_execution_authority")
    if packet.get("partner_tracking_number") is not None:
        raise ValueError("preview_tracking_number_must_remain_unassigned")
    if packet.get("routing_destination_or_sip_endpoint") is not None:
        raise ValueError("preview_cannot_include_live_route")
    if packet.get("signed_agreement_evidence") is not None:
        raise ValueError("signed_contract_cannot_be_assumed_for_review")
    formats = packet.get("publisher_format_review")
    if formats is not None:
        # The registry may contain future buyer evidence; that can never
        # silently convert this offline illustration into consumer intake.
        if (not isinstance(formats, Mapping)
                or formats.get("launch_authorized") is not False
                or formats.get("double_monetization_authorized") is not False
                or not isinstance(formats.get("PAY_PER_LEAD"), Mapping)
                or not isinstance(formats.get("PAY_PER_CALL"), Mapping)
                or formats["PAY_PER_LEAD"].get("live_form_capture_enabled") is not False
                or formats["PAY_PER_LEAD"].get("lead_delivery_enabled") is not False
                or formats["PAY_PER_CALL"].get("live_call_traffic_enabled") is not False):
            raise ValueError("live_format_authority_forbidden_in_private_preview")
    desc = PARTNER_PREVIEW_DESCRIPTORS[key]
    gates = pilot.get("activation_gates")
    if (not isinstance(gates, Mapping) or not gates
            or any(type(v) is not bool for v in gates.values())):
        raise ValueError("unverified_or_invalid_partner_launch_gates")
    # Partially verified commercial/technical gates may evolve later. That
    # must never make this offline file a customer-facing or active route.
    return {
        "schema_version": "empire.partner_landing_private_review.v1",
        "entity_key": key,
        "company_name_for_internal_review_only": str(pilot.get("company") or "")[:160],
        "mode": "OFFLINE_PRIVATE_REVIEW",
        "headline": desc["headline"],
        "subheadline": desc["summary"],
        "proposed_vertical_not_buyer_approved": desc["vertical"],
        "proposed_region_not_buyer_approved": desc["region"],
        "service_topics": list(desc["needs"]),
        "two_product_pilot_review": {
            "PAY_PER_CALL": {
                "offer_requested_not_approved": True,
                "proposed_event": "Consumer-initiated inbound call",
                "buyer_to_confirm": [
                    "Approved ZIP/postcode, job types, hours and daily cap",
                    "Call duration, quality, duplicates and chargeable event",
                    "Tracking number, real buyer route, payout and settlement",
                ],
                "route_enabled": False,
            },
            "PAY_PER_LEAD": {
                "offer_requested_not_approved": True,
                "proposed_event": "Consumer-initiated contact form enquiry",
                "buyer_to_confirm": [
                    "Approved lead fields, homeowner/job checks and ZIP/postcode",
                    "Lead price, exclusive/shared basis, caps and returns",
                    "Consent text/evidence, API contract and acceptance receipts",
                ],
                "consumer_fields_collected": False,
                "form_enabled": False,
                "delivery_enabled": False,
            },
            "same_enquiry_double_sale_approved": False,
            "canonical_consumer_lead_receipt_verified": False,
            "buyer_programme_confirmed": False,
        },
        "self_owned_illustration": desc["image"],
        "review_notice": "PRIVATE REVIEW — buyer approval, geographic coverage and call routing pending",
        "customer_notice": (
            "This is a service-information concept, not an offer of coverage. "
            "No provider, pricing or availability has been confirmed. "
            "No request or call can be submitted through this preview."
        ),
        "approval_checklist": list(gates),
        "approval_gates": dict(gates),
        "tracking_number": None,
        "call_action_enabled": False,
        "lead_form_enabled": False,
        "external_tracking_enabled": False,
        "buyer_logo_used": False,
        "buyer_disclosure_approved": False,
        "published": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
    }


def render_partner_landing_review_html(review: Mapping[str, Any]) -> str:
    """Self-contained, offline, no-PHI / no-PII review for a human approver."""
    from html import escape

    if not isinstance(review, Mapping) or review.get("schema_version") != (
        "empire.partner_landing_private_review.v1"
    ):
        raise ValueError("unexpected_private_landing_schema")
    if review.get("call_action_enabled") is not False or review.get("published") is not False:
        raise ValueError("preview_cannot_enable_live_traffic")
    if review.get("tracking_number") is not None or review.get("lead_form_enabled") is not False:
        raise ValueError("preview_cannot_capture_or_route")
    if review.get("execution_authority") != "NONE":
        raise ValueError("preview_execution_authority_must_be_none")
    if review.get("entity_key") not in PARTNER_PREVIEW_DESCRIPTORS:
        raise ValueError("unknown_private_landing_partner")
    formats = review.get("two_product_pilot_review")
    if (not isinstance(formats, Mapping)
            or formats.get("buyer_programme_confirmed") is not False
            or formats.get("same_enquiry_double_sale_approved") is not False
            or formats.get("canonical_consumer_lead_receipt_verified") is not False
            or not isinstance(formats.get("PAY_PER_CALL"), Mapping)
            or not isinstance(formats.get("PAY_PER_LEAD"), Mapping)
            or formats["PAY_PER_CALL"].get("route_enabled") is not False
            or formats["PAY_PER_LEAD"].get("form_enabled") is not False
            or formats["PAY_PER_LEAD"].get("delivery_enabled") is not False
            or formats["PAY_PER_LEAD"].get("consumer_fields_collected") is not False):
        raise ValueError("private_review_rejects_enabled_products")
    image = review.get("self_owned_illustration")
    if image not in (None, "roofing-hero.webp"):
        raise ValueError("untrusted_preview_media")
    e = lambda key: escape(str(review[key]), quote=True)
    topic_html = "".join(
        '<div class="need"><span class="bullet">✓</span>' + escape(str(item)) + '</div>'
        for item in review["service_topics"]
    )
    def product_panel(key: str, label: str) -> str:
        details = formats[key]
        fields = details.get("buyer_to_confirm")
        if (details.get("offer_requested_not_approved") is not True
                or not isinstance(fields, list)
                or not 1 <= len(fields) <= 8
                or any(not isinstance(item, str) or len(item) > 160
                       for item in fields)):
            raise ValueError("invalid_offline_product_requirements")
        items = "".join(
            '<div class="need"><span class="bullet">•</span>'
            + escape(item) + '</div>' for item in fields
        )
        return ('<section class="panel"><h2>' + escape(label) +
                ' — under review</h2><p>' +
                escape(str(details.get("proposed_event") or "")) +
                '</p>' + items + '</section>')
    products_html = (
        product_panel("PAY_PER_CALL", "Pay Per Call")
        + product_panel("PAY_PER_LEAD", "Pay Per Lead")
    )
    backdrop = (
        '<img class="hero-image" src="roofing-hero.webp" alt="Roofing service example">'
        if image else '<div class="hero-shape" aria-hidden="true"></div>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="referrer" content="no-referrer">
<title>{e("headline")} | Empire AI · PRIVATE REVIEW</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, Arial, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f5f8ff; color: #071c40; }}
.review {{ background: #081b38; color: #fff; padding: 14px 5%; display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap; font-size: 12px; letter-spacing: .04em; }}
.logo {{ font-weight: 900; font-size: 20px; letter-spacing: -.035em; }}
.tag {{ border: 1px solid #65d8ff; color: #a7efff; border-radius: 99px; padding: 8px 13px; font-weight: 700; }}
.wrapper {{ max-width: 1220px; margin: auto; padding: 0 30px; }}
.hero {{ overflow: hidden; background: linear-gradient(130deg,#e1f2ff,#f9fcff 54%,#dceaff); }}
.hero-grid {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 44px; align-items: center; padding: 82px 0; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .16em; color: #1266d8; font-size: 12px; font-weight: 800; }}
h1 {{ font-size: clamp(42px,5.2vw,70px); max-width: 720px; line-height: 1.04; letter-spacing: -.055em; margin: 19px 0; }}
p {{ font-size: 17px; line-height: 1.65; color: #436185; }}
.hero-image {{ width: 100%; height: 420px; object-fit: cover; border-radius: 24px; box-shadow: 0 32px 72px #12386d30; }}
.hero-shape {{ width: 100%; height: 380px; border-radius: 24px; background: radial-gradient(circle at 30% 28%,#57c8ff,transparent 46%),linear-gradient(140deg,#035abf,#09254d 75%); box-shadow: 0 32px 72px #12386d30; }}
.cta {{ appearance: none; border: 0; background: #d5deec; color: #52667d; padding: 18px 26px; border-radius: 12px; font-size: 15px; font-weight: 800; font-family: inherit; cursor: not-allowed; margin-top: 23px; }}
.cols {{ display:grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 40px 0; }}
.panel {{ border: 1px solid #dce9f9; background: white; border-radius: 20px; padding: 32px; box-shadow:0 8px 28px #2148780a; }}
h2 {{ font-size: 22px; letter-spacing: -.03em; margin: 0 0 19px; }}
.need {{ display:flex; gap:12px; align-items:center; border-bottom: 1px solid #eaf0f7; padding:14px 0; font-weight: 700; }}
.bullet {{ color: #0d70d1; }}
footer {{ padding:36px 30px; border-top: 1px solid #d7e5f5; font-size: 13px; line-height: 1.6; color: #5a6f8a; }}
@media(max-width:770px) {{ .hero-grid, .cols {{ grid-template-columns: 1fr; }} .hero-grid {{ padding: 44px 0; }} .hero-image,.hero-shape {{ height:260px; }} }}
</style>
</head>
<body>
<header class="review"><span class="logo">EMPIRE AI</span><span class="tag">{e("review_notice")}</span></header>
<main>
<section class="hero">
<div class="wrapper hero-grid">
<div>
<div class="eyebrow">Service information · review-only concept</div>
<h1>{e("headline")}</h1>
<p>{e("subheadline")}</p>
<button class="cta" type="button" disabled aria-disabled="true">Call route not available — review pending</button>
<p><small>No consumer call, form, quote or provider match is enabled.</small></p>
</div>
{backdrop}
</div>
</section>
<div class="wrapper cols">
<section class="panel"><h2>Project types being considered</h2>{topic_html}</section>
<section class="panel"><h2>Availability is subject to review</h2>
<p>{e("proposed_region_not_buyer_approved")}</p>
<p>Property location, hours, coverage, eligibility and consent requirements must be independently approved before any live campaign.</p>
</section>
</div>
<div class="wrapper cols">{products_html}</div>
<div class="wrapper"><p><strong>Commercial hold:</strong> No live consumer data capture, buyer delivery, call routing or billing. Both programmes and the treatment of a duplicate call/form enquiry require separate written approval.</p></div>
</main>
<footer class="wrapper">{e("customer_notice")} This page is an unpublished, offline preview for internal buyer review only.</footer>
</body>
</html>
"""
