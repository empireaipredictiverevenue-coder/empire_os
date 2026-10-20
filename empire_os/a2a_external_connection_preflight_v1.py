"""A2A Meta + Finance connector readiness (no provider network calls).

Credentials and ID presence alone are never sufficient for account trust,
automation authority or payment activation. This module outputs only booleans,
non-secret blockers, and the accountable external-account setup tasks.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "empire.a2a.external_connector_readiness.v1"
AGENT_ID = "empire.a2a.commercial_signal_miner.v1"
REQUIRED = {
    "meta": (
        "META_APP_ID", "META_APP_SECRET", "META_PAGE_ID",
        "META_IG_BUSINESS_ACCOUNT_ID", "META_PAGE_ACCESS_TOKEN",
    ),
    "stripe": (
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    ),
}
# These names are the *proposed* EmpireOS configuration contract, not
# existing production config conventions or claims about Meta-approved scopes.
META_SCOPES_TO_REQUEST_SUBJECT_TO_REVIEW = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "pages_messaging",
    "instagram_basic",
    "instagram_manage_comments",
    "instagram_content_publish",
    "instagram_manage_messages",
)


def _truth(value: Any) -> bool:
    return value is True


def review_connections(
    configured: Mapping[str, bool],
    *,
    account_readback_verified: bool = False,
    meta_permissions_verified: bool = False,
    meta_business_assets_verified: bool = False,
    payment_provider_test_verified: bool = False,
    payment_webhook_signature_verified: bool = False,
    live_payment_authorized_by_finance_owner: bool = False,
) -> dict[str, Any]:
    """Build actionable blockers; never grant capabilities from self-attestation.

    Status arguments are *operator claims*, not source-authenticated receipts.
    This inspection cannot itself authenticate OAuth, Stripe, or Meta approval.
    """
    if not isinstance(configured, Mapping) or any(type(v) is not bool for v in configured.values()):
        raise ValueError("boolean_config_presence_only")
    presence = {
        provider: {name: configured.get(name) is True for name in fields}
        for provider, fields in REQUIRED.items()
    }
    meta_missing = [k for k,v in presence["meta"].items() if not v]
    stripe_missing = [k for k,v in presence["stripe"].items() if not v]
    meta_holds = []
    if meta_missing:
        meta_holds.append("META_OAUTH_AND_ASSET_BINDING_NOT_COMPLETE")
    if not _truth(account_readback_verified) or not _truth(meta_business_assets_verified):
        meta_holds.append("META_PAGE_AND_INSTAGRAM_ASSETS_NOT_LIVE_VERIFIED")
    if not _truth(meta_permissions_verified):
        meta_holds.append("META_SCOPES_APP_REVIEW_AND_ACCOUNT_POLICY_UNVERIFIED")
    stripe_holds = []
    if stripe_missing:
        stripe_holds.append("STRIPE_TEST_KEYS_AND_SIGNED_WEBHOOK_NOT_CONFIGURED")
    if not _truth(payment_provider_test_verified):
        stripe_holds.append("STRIPE_SANDBOX_CHECKOUT_AND_RECEIPT_NOT_VERIFIED")
    if not _truth(payment_webhook_signature_verified):
        stripe_holds.append("STRIPE_WEBHOOK_SIGNATURE_RECONCILIATION_NOT_VERIFIED")
    if not _truth(live_payment_authorized_by_finance_owner):
        stripe_holds.append("FINANCE_OWNER_HAS_NOT_AUTHORIZED_LIVE_PAYMENT_EXECUTION")
    return {
        "schema_version": SCHEMA, "agent_id": AGENT_ID,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "meta": {
            "provider": "Meta Graph API",
            "configured_required_presence": presence["meta"],
            "missing_prerequisites": meta_missing,
            "blockers": meta_holds,
            "verified_business_account_connection": False,
            "social_read_live": False,
            "social_publish_enabled": False,
            "messenger_or_instagram_dm_enabled": False,
            "unapproved_group_collection": False,
            "candidate_scopes_require_up_to_date_official_review":
                list(META_SCOPES_TO_REQUEST_SUBJECT_TO_REVIEW),
            "next_owner": "meta_business_admin_and_social_integration_owner",
        },
        "stripe": {
            "provider": "Stripe",
            "configured_required_presence": presence["stripe"],
            "missing_prerequisites": stripe_missing,
            "blockers": stripe_holds,
            "verified_sandbox_payment_provider_connection": False,
            "payment_links_created": 0, "real_payments_authorized": False,
            "client_bank_or_card_data_exposed_to_agent": False,
            "next_owner": "finance_os_payment_integration_owner",
        },
        "required_user_actions": [
            "Authorise the specific Empire AI Facebook Page and professional Instagram account",
            "Authorise documented Meta app scopes and pass app-review and Page access requirements",
            "Connect the business Stripe account through approved OAuth/provider setup",
            "Complete a signed Stripe sandbox checkout and webhook reconciliation",
            "Get separate founder and Finance OS owner permission before publishing or live payment",
        ],
        "connector_presence_does_not_prove_actual_permission": True,
        "account_connections_performed_by_this_review": False,
        "secret_values_in_output": False,
        "production_gateway_modified": False,
    }
