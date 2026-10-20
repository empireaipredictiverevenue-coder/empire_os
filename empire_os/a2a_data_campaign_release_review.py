"""Bind data campaign experiments to independent source-specific release gates.

A research ranking is not a marketing permission. Even an apparent cleared source
cannot authorise campaigns without typed approvals from owner control systems.
"""
from __future__ import annotations

from typing import Any, Mapping
from empire_os.a2a_data_campaign_experiments import SCHEMA as CAMPAIGN_SCHEMA
from empire_os.a2a_nyc_commercial_evidence_gate import SCHEMA as NYC_SCHEMA

SCHEMA = "empire.a2a.data_campaign_source_release_review.v1"


def assess_campaign_readiness(
    experiments: Mapping[str, Any],
    nyc_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(experiments, Mapping) or experiments.get("schema_version") != CAMPAIGN_SCHEMA:
        raise ValueError("invalid_campaign_experiments")
    if not isinstance(nyc_preflight, Mapping) or nyc_preflight.get("schema_version") != NYC_SCHEMA:
        raise ValueError("invalid_nyc_source_review")
    if experiments.get("execution_authority") != "NONE" or nyc_preflight.get("execution_authority") != "NONE":
        raise ValueError("untrusted_source_authority")
    for name, packet in (("experiments", experiments), ("nyc", nyc_preflight)):
        if (packet.get("spend_authorised") is True or packet.get("outbound_sent") is True
                or packet.get("campaign_launch_authorized") is True
                or packet.get("campaigns_launched", 0) not in (0, None)):
            raise ValueError("unexpected_executing_" + name)
    campaigns = experiments.get("campaigns")
    if not isinstance(campaigns, list) or len(campaigns) > 10:
        raise ValueError("invalid_campaign_list")
    reviewed = []
    seen = set()
    for campaign in campaigns:
        if not isinstance(campaign, Mapping):
            raise ValueError("unstructured_campaign")
        cid = campaign.get("campaign_id")
        if not isinstance(cid, str) or not cid.startswith("research-only-") or cid in seen:
            raise ValueError("invalid_or_duplicate_campaign")
        seen.add(cid)
        if any(campaign.get(k) is not False for k in
               ("publishing_authorised", "outbound_authorised", "spend_authorised", "payment_created")):
            raise ValueError("campaign_authority_mismatch")
        segment = campaign.get("segment")
        if not isinstance(segment, Mapping):
            raise ValueError("missing_segment")
        niche, metro = segment.get("vertical"), segment.get("metro")
        reasons = [
            "FOUNDER_CAMPAIGN_RELEASE_NOT_APPROVED",
            "CONSENT_TRACKING_AND_COPY_NOT_APPROVED",
            "BUYER_INTENT_AND_CONVERSION_NOT_INDEPENDENTLY_VERIFIED",
        ]
        if niche == "general_contractor" and metro == "nyc":
            if campaign.get("product_proposal", {}).get("product_id") != "nyc_permit_project_verification":
                raise ValueError("nyc_product_mapping_mismatch")
            reasons.extend(nyc_preflight.get("hold_reasons") or [])
            reason = "NYC_DATA_RIGHTS_AND_BUYER_PRECHECK"
            report_ref = "nyc_commercial_preflight.json"
            if nyc_preflight.get("source", {}).get("digest_matches") is not True:
                reasons.append("NYC_PROVENANCE_INTEGRITY_NOT_CONFIRMED")
        else:
            reasons.append("NO_SOURCE_SPECIFIC_PRODUCT_RIGHTS_AUDIT_FOR_THIS_SEGMENT")
            reason = "OTHER_PRODUCT_OWNER_PRECHECK_REQUIRED"
            report_ref = None
        reviewed.append({
            "campaign_id": cid,
            "sector": niche, "metro": metro,
            "evidence_gate": reason,
            "source_review_document": report_ref,
            "hold_reasons": sorted(set(reasons)),
            "campaign_research_review_allowed": True,
            "source_ready_for_customer_distribution": False,
            "commercial_buyer_verified": False,
            "live_campaign_authorized": False,
            "ad_spend_authorized": False,
            "personal_social_targeting_authorized": False,
            "publish_or_outbound_authorized": False,
            "next_owner": ("data_brokerage_and_buyer_scout" if report_ref else
                           "product_rights_and_buyer_scout"),
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "reviewed_campaign_count": len(reviewed),
        "launch_ready_campaign_count": 0,
        "campaigns_blocked_pending_gates": len(reviewed),
        "campaigns": reviewed,
        "actual_commercial_launches": 0,
        "messages_sent": False, "payments_issued": False, "data_resale_started": False,
        "next_action": "COMPLETE_SOURCE_RIGHTS_BUYER_AND_CAMPAIGN_APPROVALS",
    }
