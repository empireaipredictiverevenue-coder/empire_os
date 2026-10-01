"""Person-bound commercial offer readiness.

Architecture contract:

Opportunity Factory remains the strict autonomous market-execution gate.

This module answers a narrower commercial question:

    Do we have a real target plus a currently verified product
    from which a governed proposal can be prepared?

It NEVER:
- claims verified buyer demand from research fit;
- treats price as expected revenue;
- authorizes outbound;
- overrides suppression;
- accepts terms;
- moves funds;
- recognizes revenue.

Live sending remains founder gated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


SCHEMA_VERSION = "empire.predictive-revenue.commercial-offer-book.v2"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def product_ready(product: Mapping[str, Any]) -> bool:
    price = product.get("price_basis")

    if not isinstance(price, Mapping):
        return False

    amount_cents = price.get("amount_cents")
    currency = _clean(
        price.get("currency")
        or product.get("currency")
    )
    unit = _clean(price.get("unit"))

    return (
        product.get("active") is True
        and product.get("binding_terms_ready") is True
        and str(
            product.get("catalog_state") or ""
        ).upper() == "VERIFIED"
        and str(
            product.get("version_state") or ""
        ).upper() == "VERIFIED"
        and type(amount_cents) is int
        and amount_cents > 0
        and bool(currency)
        and bool(unit)
        and not (product.get("readiness_blockers") or [])
    )


def _ready_catalog(
    catalog: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}

    for row in catalog.get("products") or []:
        if not isinstance(row, Mapping):
            continue

        code = _clean(row.get("product_code"))

        if code and product_ready(row):
            result[code] = row

    return result


def _product_projection(
    product: Mapping[str, Any],
) -> dict[str, Any]:
    price = product.get("price_basis") or {}

    return {
        "product_id": product.get("product_id"),
        "product_code": product.get("product_code"),
        "product_name": product.get("product_name"),
        "product_family": product.get("product_family"),
        "billing_model": product.get("billing_model"),
        "binding_terms_ready":
            product.get("binding_terms_ready"),
        "catalog_state": product.get("catalog_state"),
        "version_state": product.get("version_state"),
        "verified_at": product.get("verified_at"),

        # Offer price, NOT predicted or realized revenue.
        "amount_cents": price.get("amount_cents"),
        "currency":
            price.get("currency")
            or product.get("currency"),
        "unit": price.get("unit"),

        "price_basis": price,
        "evidence_refs":
            product.get("evidence_refs") or [],
    }


def build_commercial_offer_book(
    *,
    catalog: Mapping[str, Any],
    revenue_distribution: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(
        timezone.utc
    ).isoformat()

    ready_catalog = _ready_catalog(catalog)

    review_rows = revenue_distribution.get(
        "human_review_queue"
    )
    review_rows = (
        review_rows
        if isinstance(review_rows, list)
        else []
    )

    rows: list[dict[str, Any]] = []

    for source in review_rows:
        if not isinstance(source, Mapping):
            continue

        source_codes = source.get("product_codes")
        source_codes = (
            source_codes
            if isinstance(source_codes, list)
            else []
        )

        source_codes = tuple(
            dict.fromkeys(
                _clean(code)
                for code in source_codes
                if _clean(code)
            )
        )

        ready_codes = tuple(
            code
            for code in source_codes
            if code in ready_catalog
        )

        unready_codes = tuple(
            code
            for code in source_codes
            if code not in ready_catalog
        )

        person_verified = (
            source.get("person_verified") is True
        )

        email_verified = (
            source.get("email_verified") is True
        )

        product_ready_now = bool(ready_codes)

        offer_package_ready = (
            person_verified
            and email_verified
            and product_ready_now
        )

        if offer_package_ready:
            state = "OFFER_READY"
        elif not product_ready_now:
            state = "PRODUCT_READINESS_REQUIRED"
        elif not person_verified or not email_verified:
            state = "CONTACT_EVIDENCE_REQUIRED"
        else:
            state = "REVIEW_REQUIRED"

        conversation_refs = tuple(
            source.get("conversation_refs") or ()
        )

        send_blockers = [
            "founder_live_outbound_approval_required",
            "live_outbound_authority_required",
            "current_canonical_suppression_and_inbox_check",
        ]

        if not conversation_refs:
            send_blockers.append(
                "existing_thread_or_new_outreach_context_review"
            )

        # Preserve meaningful source blockers.
        for blocker in (
            source.get("readiness_blockers") or []
        ):
            blocker = _clean(blocker)

            if blocker and blocker not in send_blockers:
                send_blockers.append(blocker)

        rows.append({
            "state": state,

            "canonical_prospect_id":
                source.get("canonical_prospect_id"),

            "company": source.get("company"),
            "domain": source.get("domain"),

            "person_name":
                source.get("person_name"),

            "person_verified": person_verified,

            "email": source.get("email"),

            "email_verified": email_verified,

            "email_verification_scope":
                source.get(
                    "email_verification_scope"
                ),

            "commercial_role":
                source.get("commercial_role"),

            "commercial_authority_verified":
                source.get(
                    "commercial_authority_verified"
                ) is True,

            "demand_state":
                source.get("demand_state")
                or "UNKNOWN",

            "buyer_demand_verified": (
                str(
                    source.get("demand_state")
                    or ""
                ).upper()
                == "VERIFIED"
            ),

            "conversation_state":
                source.get("conversation_state"),

            "conversation_refs":
                list(conversation_refs),

            "contact_mode": (
                "EXISTING_THREAD_REVIEW"
                if conversation_refs
                else "NEW_OUTREACH_REVIEW"
            ),

            "source_product_codes":
                list(source_codes),

            "ready_product_codes":
                list(ready_codes),

            "unready_product_codes":
                list(unready_codes),

            "products": [
                _product_projection(
                    ready_catalog[code]
                )
                for code in ready_codes
            ],

            "offer_package_ready":
                offer_package_ready,

            # Never infer forecast revenue from catalogue price.
            "expected_revenue_cents": None,

            "actual_revenue": False,

            # Deliberately false until separate governed checks.
            "live_send_ready": False,
            "live_outbound_authorized": False,
            "execution_authority": "none",

            "send_blockers":
                list(dict.fromkeys(send_blockers)),

            "evidence_refs":
                source.get("evidence_refs") or [],
        })

    state_order = {
        "OFFER_READY": 0,
        "CONTACT_EVIDENCE_REQUIRED": 1,
        "PRODUCT_READINESS_REQUIRED": 2,
        "REVIEW_REQUIRED": 3,
    }

    rows.sort(
        key=lambda row: (
            state_order.get(row["state"], 99),
            0
            if row["contact_mode"]
            == "EXISTING_THREAD_REVIEW"
            else 1,
            str(row.get("company") or ""),
            str(row.get("domain") or ""),
        )
    )

    offer_ready = [
        row
        for row in rows
        if row["state"] == "OFFER_READY"
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,

        "catalog_generated_at":
            catalog.get("generated_at"),

        "revenue_distribution_generated_at":
            revenue_distribution.get("generated_at"),

        "execution_authority": "none",
        "outreach_authority": "none",
        "payment_authority": "none",

        "actual_revenue": False,

        "ready_catalog_product_count":
            len(ready_catalog),

        "review_target_count":
            len(rows),

        "offer_ready_count":
            len(offer_ready),

        "definition": {
            "OFFER_READY": (
                "person and email verified in current "
                "review material plus at least one "
                "currently verified, binding-ready, "
                "priced catalogue product"
            ),
            "LIVE_SEND_READY": (
                "always false in this artifact; "
                "canonical suppression/inbox checks "
                "and founder live-outbound approval "
                "remain separate gates"
            ),
            "buyer_demand": (
                "research product fit does not establish "
                "verified buyer demand"
            ),
        },

        "offer_ready": offer_ready,
        "targets": rows,
    }
