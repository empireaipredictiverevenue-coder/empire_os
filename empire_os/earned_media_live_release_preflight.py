"""Read-only public enquiry + private CRM boundary release evidence.

Uses the existing first-sale canary only, and never interprets a health result
as contact consent, a credited source, customer delivery or deployment approval.
Founder Console ingress/session verification is independent and deliberately held.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

SCHEMA = "empire.earned_media.live_release_preflight.v1"
CANARY_SCHEMA = "empire.founder.live_sales_page_readonly_canary.v1"
CONVERSION_SCHEMA = "empire.earned_media.first_party_conversion_review.v1"


def assess_release(
    first_party: Mapping[str, Any],
    *,
    public: Mapping[str, Any] | None,
    private_crm: Mapping[str, Any] | None,
    private_founder_ingress_verified: bool = False,
) -> dict[str, Any]:
    """Never grant release from a caller assertion or a loopback GET."""
    source_ready = (
        isinstance(first_party, Mapping)
        and first_party.get("schema_version") == CONVERSION_SCHEMA
        and first_party.get("mode") == "OBSERVE"
        and first_party.get("execution_authority") == "none"
        and first_party.get("state") ==
            "STAGED_EXISTING_GUIDE_TO_EXISTING_INTAKE_NOT_LIVE_VERIFIED"
        and first_party.get("reviewed_entry_page") == "/predictive-revenue"
        and first_party.get("source_code_readiness") is True
        and first_party.get("founder_site_release_authorized") is False
        and first_party.get("consented_enquiry_verified") is False
        and first_party.get("realised_revenue_verified") is False
        and first_party.get("publication_executed") is False
        and first_party.get("smart_crm_writes") is False
    )
    public_ok = (
        isinstance(public, Mapping)
        and public.get("schema_version") == CANARY_SCHEMA
        and public.get("mode") == "READ_ONLY"
        and public.get("status") == "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN"
        and public.get("public_page_count") == 2
        and public.get("compiled_intake_routes_verified") == 2
        and type(public.get("commercial_offer_count")) is int
        and 1 <= public["commercial_offer_count"] <= 100
        and type(public.get("predictive_revenue_product_count")) is int
        and 1 <= public["predictive_revenue_product_count"] <= 100
        and public.get("database_writes") is False
        and public.get("genuine_test_buyer_submitted") is False
        and public.get("founder_crm_delivery_verified") is False
        and public.get("outbound_sent") is False
        and public.get("checkout_or_payment_executed") is False
    )
    crm_ok = (
        isinstance(private_crm, Mapping)
        and private_crm.get("private_crm_auth_boundary_checked") is True
        and private_crm.get("private_crm_auth_boundary_verified") is True
        and private_crm.get("private_crm_healthy") is True
        and private_crm.get("anonymous_prospect_access_denied") is True
        and private_crm.get("anonymous_buyer_access_denied") is True
        and private_crm.get("private_crm_customer_rows_read") is False
        and private_crm.get("founder_login_authenticated") is False
        and private_crm.get("founder_crm_delivery_verified") is False
    )
    # This flag may be supplied by a test, but never itself proves real auth:
    # it is reported as UNVERIFIED until an independent live ingress audit,
    # session verifier, and deployment owner release actually exist.
    # Never add automatic release logic on the basis of this boolean.
    del private_founder_ingress_verified
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "HELD_PRIVATE_AUTH_AND_PRODUCTION_RELEASE",
        "source_code_review_ready": source_ready,
        "public_original_enquiry_gets_verified": public_ok,
        "public_catalogue_gets_verified": public_ok,
        "private_crm_anonymous_denial_verified": crm_ok,
        "private_founder_console_ingress_verified": False,
        "private_founder_session_verified": False,
        "existing_public_route_used": "/predictive-revenue",
        "existing_enquiry_route_used": "/commercial#commercial-enquiry",
        "new_staged_cta_deployed_verified": False,
        "new_staged_private_screen_deployed_verified": False,
        "article_editorial_publication_authorized": False,
        "source_clicked_verified": False,
        "source_attributed_consented_enquiry_verified": False,
        "actual_customer_receipts_read": False,
        "canonical_smart_crm_delivery_verified": False,
        "authenticated_founder_login_tested": False,
        "contract_terms_accepted_verified": False,
        "realised_revenue_gbp_minor": None,
        "launch_approval": False,
        "founder_site_release_authorized": False,
        "sender_authority": False, "crm_write_authority": False,
        "payment_authority": False, "publisher_contact_authority": False,
        "publication_executed": False, "website_deployment_executed": False,
        "messages_sent": False, "lead_ingest_performed": False,
        "database_writes": False, "money_moved": False,
        "release_hold_reasons": [
            *([] if source_ready else ["ORIGINAL_CONTENT_CONVERSION_SOURCE_HELD"]),
            *([] if public_ok else ["PUBLIC_FIRST_PARTY_GET_CANARY_UNVERIFIED"]),
            *([] if crm_ok else ["EXISTING_PRIVATE_CRM_ANONYMOUS_BOUNDARY_UNVERIFIED"]),
            "PRIVATE_FOUNDER_INGRESS_AND_SESSION_NOT_INDEPENDENTLY_VERIFIED",
            "SITE_OWNER_ASTRA_AND_FOUNDER_RELEASE_NOT_APPROVED",
            "ACTUAL_DEPLOYED_NEW_CTA_AND_NEW_PRIVATE_ROUTE_UNVERIFIED",
        ],
        "recommended_next_action": (
            "Founder/site owner: review the exact staged commit, prove "
            "private authenticated ingress+session and consented route "
            "without fabricating customer submissions; obtain separate "
            "release approval before deploying."
        ),
        "real_revenue_state": "NO_CANONICAL_SETTLEMENT_QUERIED",
    }


def inspect_live_release(
    first_party: Mapping[str, Any],
    *,
    public_inspector: Callable[[], Mapping[str, Any]] | None = None,
    crm_inspector: Callable[[], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Opt-in GET-only local canary, never part of public request handling."""
    from scripts import probe_first_party_sales_http_readonly as canary

    p = public_inspector or canary.inspect
    c = crm_inspector or canary.inspect_private_crm_auth
    try:
        public = p()
    except Exception:
        public = None
    try:
        private = c()
    except Exception:
        private = None
    return assess_release(first_party, public=public, private_crm=private)
