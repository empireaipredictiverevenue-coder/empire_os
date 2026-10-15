"""Adapter for genuine canonical EmpireDB reviewer membership, prepared-only.

A root-signed GTM roster is *necessary but insufficient*: every signature
also requires a current membership fetched through EmpireOS's EXISTING
dedicated, least-privilege CRM membership reader. No new login, role, table,
grant or duplicate database is created here. Fail closed until first-party
tenant identity and independent human reviewers are really provisioned.

V2 requires only the purpose-built GTM_RESEARCH_REVIEWER role; owner/admin,
operator, analyst and viewer cannot sign independent research reviews by
virtue of their general access. A first-party owner remains FINAL APPROVER
in the separate commercial founder gate. Existing PostgreSQL 041 membership
role CHECK migration for the new role remains PREPARED ONLY and undeployed.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader
from empire_os.saas_scale import TenantMembership
from empire_os.gtm_signed_reviewer_gate import REVIEW_SCOPE, ID


class GtmCanonicalReviewerMembership:
    """First-party authenticated membership reader with minimum privilege.

    Only accepts the existing dedicated EmpireDB reader implementation.
    The signed reviewer roster is checked independently by the caller.
    Do not create from user-submitted DSNs or tokens in an HTTP route.
    """

    def __init__(self, *, authoritative_reader: EmpireDbCrmMembershipReader,
                 expected_tenant: str) -> None:
        if type(authoritative_reader) is not EmpireDbCrmMembershipReader:
            raise ValueError("existing_canonical_membership_reader_required")
        try:
            if str(UUID(expected_tenant)) != expected_tenant:
                raise ValueError()
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("canonical_reviewer_tenant_required") from exc
        self._reader = authoritative_reader
        self._tenant = expected_tenant

    def __call__(self, reviewer_id: str, tenant_id: str, scope: str) -> bool:
        if (tenant_id != self._tenant
                or scope != REVIEW_SCOPE
                or not isinstance(reviewer_id, str)
                or ID.fullmatch(reviewer_id) is None):
            return False
        try:
            membership = self._reader(reviewer_id, tenant_id)
            return (
                isinstance(membership, TenantMembership)
                and membership.user_id == reviewer_id
                and membership.tenant_id == tenant_id
                and membership.status == "active"
                and membership.role == "gtm_research_reviewer"
                and membership.can(REVIEW_SCOPE) is True
                and membership.can("read") is False
                and membership.can("admin") is False
                and membership.can("manage_members") is False
                and membership.can("operate") is False
            )
        except Exception:
            return False
