"""EmpireOS Predictive Revenue V4.11: one fail-closed CRM/source research gate.

Reuses original CRM signed membership and EmpireDB 066 HELD rights reader.
This is NOT an execution/admission gate that can ever approve real buyers,
revenue recognition, outbound, paid media, trading, or source redistribution.
No import-time IO, database migration, new service or standalone tenant DB.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from empire_os.predictive_cloud_v410_rights_reader import (
    EmpireDbHeldSourceRightsReader, HeldRightsObservation,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
SCHEMA = "empire.predictive_revenue.v411.tenant_rights_held.v1"


class PredictiveRevenueSourceHold(ValueError):
    """Reject untrusted CRM/readers without exposing token or DB details."""


def review_revenue_source_candidate_held(
    *,
    crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    source_rights_reader: EmpireDbHeldSourceRightsReader,
    source_evidence_digest: str,
) -> dict[str, Any]:
    """Return a non-promotable opportunity/source observation, never authority.

    The signed CRM principal is obtained from first-party pinned-key login +
    canonical active membership. The rights result is from the exact original
    restricted EmpireDB reader, not an envelope-supplied licence verdict.
    """
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise PredictiveRevenueSourceHold("original_crm_membership_verifier_required")
    if type(source_rights_reader) is not EmpireDbHeldSourceRightsReader:
        raise PredictiveRevenueSourceHold("original_empiredb_rights_reader_required")
    if type(crm_bearer) is not str or not 1 <= len(crm_bearer) <= 4096:
        raise PredictiveRevenueSourceHold("signed_crm_bearer_required")
    if type(source_evidence_digest) is not str or not _SHA256.fullmatch(source_evidence_digest):
        raise PredictiveRevenueSourceHold("source_digest_invalid")

    try:
        tenant_id = crm_verifier.authenticate(crm_bearer)
        if type(tenant_id) is not str or str(UUID(tenant_id)) != tenant_id or UUID(tenant_id).int == 0:
            raise ValueError("invalid CRM tenant ID")
    except Exception:
        raise PredictiveRevenueSourceHold("crm_identity_or_active_membership_held") from None

    # Database 066 is not live yet: missing function, login or permissions must
    # give None / HELD. This is not approval to activate those resources.
    try:
        observation = source_rights_reader(tenant_id, source_evidence_digest)
    except Exception:
        observation = None
    trustworthy = (
        type(observation) is HeldRightsObservation
        and observation.tenant_id == tenant_id
        and observation.source_evidence_digest == source_evidence_digest
        and type(observation.revoked) is bool
        and observation.real_rights_independently_verified is False
        and observation.source_admission_authorized is False
        and observation.execution_authority == "none"
        and observation.decision in {
            "NO_SOURCE_RIGHTS_HELD", "PENDING_HELD",
            "CANDIDATE_REVIEW_HELD", "EXPIRED_HELD",
            "FUTURE_EVIDENCE_HELD", "REVOKED_HELD",
        }
        and (observation.decision == "REVOKED_HELD") == observation.revoked
    )
    decision = observation.decision if trustworthy else "SOURCE_RIGHTS_READER_UNAVAILABLE_HELD"
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SIGNED_CRM_MEMBER_SOURCE_RIGHTS_HELD",
        "canonical_tenant_id": tenant_id,
        "source_evidence_digest": source_evidence_digest,
        "original_signed_crm_membership_verified": True,
        "restricted_empiredb_rights_reader_checked": trustworthy,
        "rights_decision": decision,
        "real_source_rights_independently_verified": False,
        "revenue_opportunity_admitted": False,
        "customer_forecast_verified": False,
        "commercial_offer_authorized": False,
        "buyer_outreach_authorized": False,
        "lead_delivery_authorized": False,
        "redis_publish_authorized": False,
        "economic_memory_write_authorized": False,
        "recognised_revenue_cents": None,
        "paid_traffic_authorized": False,
        "trading_authorized": False,
        "funds_movement_authorized": False,
        "execution_authority": "none",
    }
