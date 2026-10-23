"""Optional agency read-only membership wrapper around EmpireOS's CANONICAL 041 reader.

Do not confuse membership with site-specific authorisation. A positive
membership is necessary but insufficient: the separately trusted site-grant
and connector registry remain mandatory in agency_connector_preflight.
"""
from __future__ import annotations

from uuid import UUID

from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader
from empire_os.saas_scale import TenantMembership


class AgencyCanonicalMembershipReader:
    """Delegate exclusively to the existing dedicated 041 membership reader.

    The caller must supply an existing reader owned by the canonical tenant
    authority. This module creates no SQL, role, DB DSN, login or live service.
    CRM signing keys and CRM bearer tokens are not accepted.
    """

    def __init__(self, *, authoritative_reader: EmpireDbCrmMembershipReader,
                 approved_tenant: str) -> None:
        if type(authoritative_reader) is not EmpireDbCrmMembershipReader:
            raise ValueError("Existing EmpireDB 041 canonical reader required")
        try:
            if type(approved_tenant) is not str or str(UUID(approved_tenant)) != approved_tenant:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Canonical approved agency tenant required") from None
        self._reader = authoritative_reader
        self._tenant = approved_tenant

    def __call__(self, subject: str, tenant_id: str) -> TenantMembership | None:
        if type(subject) is not str or not subject or tenant_id != self._tenant:
            return None
        try:
            found = self._reader(subject, tenant_id)
            if (type(found) is TenantMembership
                    and found.user_id == subject and found.tenant_id == tenant_id
                    and found.status == "active"
                    and found.role in ("owner", "admin")
                    and found.can("admin") and found.can("read")):
                return found
        except Exception:
            pass
        return None
