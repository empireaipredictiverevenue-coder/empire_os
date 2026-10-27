"""Versioned owner-review acquisition taxonomy; NEVER a live collector.

The current Analytics054 schema accepts six legacy sources. Proposed sources
are separate, require independently attested server-side source evidence, and
cannot be pushed through the original v1 ingestion or attributed to CRM.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.analytics.first_party_event_contract import ALLOWED_CHANNELS

SCHEMA = "empire.analytics.acquisition_source_v2_candidate.v1"
ORIGINAL_EVIDENCE = {
    "direct": "server_observed_direct",
    "organic_search": "server_verified_referral",
    "organic_social": "server_verified_referral",
    "referral": "server_verified_referral",
    "email": "signed_campaign_binding",
    "unknown": "server_unknown",
}
PROPOSED_EVIDENCE = {
    "paid_search": "signed_campaign_binding",
    "paid_social": "signed_campaign_binding",
    "affiliate_partner": "signed_partner_binding",
    "publisher_referral": "signed_partner_binding",
    "organic_video": "server_verified_referral",
}
ALL_EVIDENCE = {**ORIGINAL_EVIDENCE, **PROPOSED_EVIDENCE}


def review_acquisition_source_candidate(
    *, channel: str, source_evidence_kind: str,
    authenticated_owner_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate channel/evidence agreement, NOT upstream receipt authenticity.

    Raw referral URLs, cookies, click IDs, email addresses and browser claims
    are never accepted. Owner receipt material stays inside its canonical
    reader, not returned to this proposed extension.
    """
    if (type(channel) is not str or type(source_evidence_kind) is not str
            or channel not in ALL_EVIDENCE
            or ALL_EVIDENCE[channel] != source_evidence_kind):
        raise ValueError("ANALYTICS_V2_SOURCE_EVIDENCE_OR_CHANNEL_UNVERIFIED")
    if authenticated_owner_receipt is not None and (
            not isinstance(authenticated_owner_receipt, Mapping)
            or set(authenticated_owner_receipt) != {
                "verified_by_original_server_owner",
                "owner_reader_source", "property_bound",
                "privacy_source_purpose_approved",
            }
            or type(authenticated_owner_receipt["verified_by_original_server_owner"]) is not bool
            or type(authenticated_owner_receipt["property_bound"]) is not bool
            or type(authenticated_owner_receipt["privacy_source_purpose_approved"]) is not bool
            or authenticated_owner_receipt["owner_reader_source"] !=
                "ORIGINAL_ANALYTICS_AUTHENTICATED_SOURCE_READER"):
        raise ValueError("ANALYTICS_V2_UNTRUSTED_SOURCE_RECEIPT")
    claimed = authenticated_owner_receipt or {}
    owner_asserted = (claimed.get("verified_by_original_server_owner") is True
                      and claimed.get("property_bound") is True
                      and claimed.get("privacy_source_purpose_approved") is True)
    return {
        "schema_version": SCHEMA,
        "mode": "REVIEW_ONLY",
        "candidate_channel": channel,
        "source_evidence_kind": source_evidence_kind,
        "original_v1_schema_channel": channel in ALLOWED_CHANNELS,
        "new_schema_release_required": channel in PROPOSED_EVIDENCE,
        "original_owner_source_attestation_asserted": owner_asserted,
        "owner_receipt_independently_authenticated_by_this_function": False,
        "v2_database_migration_deployed_verified": False,
        "v2_collector_active": False,
        "crm_conversions_attributed": False,
        "finance_settlement_attributed": False,
        "browser_claim_sufficient": False,
        "source_attribution_authorized": False,
        "media_spend_authorized": False,
        "new_database_or_tracking_service": False,
        "execution_authority": "NONE",
    }
