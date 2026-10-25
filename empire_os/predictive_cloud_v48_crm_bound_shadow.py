"""Predictive Cloud V4.8: reuse original signed CRM reader in held admission.

No alternate identity system or new keys, roles, production DB sessions,
network clients, API mounts or workers. The injected verifier must be the
existing SignedCrmTenantVerifier, independently owned by authenticated CRM.
All outputs remain HELD fixture-only even when the CRM fixture token passes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from empire_os.predictive_cloud_v47_admission_shadow import (
    FixtureRevocations, FixtureTrustRoots, V47AdmissionHold,
    review_signed_source_fixture,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier


class V48MembershipHold(ValueError):
    """Reject missing, untrusted or mismatched CRM identity without promotion."""


def review_crm_bound_admission_fixture(
    envelope: object,
    *,
    signed_crm_bearer: object,
    crm_verifier: SignedCrmTenantVerifier,
    canonical_row: object,
    trust_roots: FixtureTrustRoots,
    revocations: FixtureRevocations,
    now: datetime,
) -> dict[str, Any]:
    """Fixture identity gate; never assert live source rights or send authority.

    crm_verifier must come from *trusted upstream* with pinned login keys
    and the original restricted EmpireDbCrmMembershipReader. A caller may not
    manufacture membership via envelope fields. Real owner authority and
    source licences require independent operational evidence.
    """
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise V48MembershipHold("original_crm_verifier_required")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise V48MembershipHold("signed_crm_bearer_required")
    try:
        # This existing verifier cryptographically validates a pinned issuer,
        # exact tenant claim, short lifetime and fresh active tenant membership.
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        # Never reflect bearer/token or DB/driver details in diagnostics.
        raise V48MembershipHold("crm_identity_or_membership_not_authorized") from None
    try:
        reviewed = review_signed_source_fixture(
            envelope, expected_tenant_id=tenant, canonical_row=canonical_row,
            trust_roots=trust_roots, revocations=revocations, now=now,
        )
    except V47AdmissionHold as exc:
        raise V48MembershipHold("source_admission_held:" + str(exc)) from None
    if reviewed.get("tenant_id") != tenant:
        raise V48MembershipHold("signed_tenant_source_mismatch")
    return {
        **reviewed,
        "schema_version": "empire.predictive_cloud.v48.crm_bound_fixture.v1",
        "status": "CRM_AND_SOURCE_FIXTURES_CRYPTOGRAPHICALLY_REVIEWED_HELD",
        "original_crm_bearer_checked": True,
        "original_crm_membership_check_completed": True,
        "original_source_dual_signature_fixture_checked": True,
        "live_production_crm_membership_attested": False,
        "live_source_key_registry_attested": False,
        "real_source_rights_independently_verified": False,
        "production_source_admitted": False,
        "redis_publish_authorized": False,
        "execution_authority": "none",
        "recognized_revenue_cents": None,
    }
