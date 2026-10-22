"""Prepare an agency connector secret only after canonical signed + site authority.

No runtime is launched by this module. Never accept CRM bearer tokens as agency
identity or permit a registry value to mint its own membership/site rights.
"""
from __future__ import annotations

import hmac
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Any

from empire_os.saas_scale import TenantMembership
from empire_os.agency_connector_authority import (
    AgencySiteGrant, authorize_agency_connector, AuthorizedConnectorRead,
)
from empire_os.agency_connector_credentials import read_private_connector_password
from empire_os.tenant_isolation import TenantResourceRef, authorize_tenant_resource


@dataclass(frozen=True)
class CanonicalConnectorBinding:
    """Fresh owner-controlled registry row, not a self-asserted JSON envelope."""
    tenant_id: str
    site_id: str
    connector_id: str
    credential_ref: str
    wp_origin: str
    allowed_operations: tuple[str, ...]
    active: bool
    read_only: bool


@dataclass(frozen=True)
class SealedAgencyReadSession:
    authority: AuthorizedConnectorRead
    # Secret is not included in repr/metadata. Keep in trusted server process only.
    _application_password: str = field(repr=False, compare=False)

    def nonsecret_receipt(self) -> dict[str, Any]:
        return {
            "tenant_id": self.authority.tenant_id,
            "site_id": self.authority.site_id,
            "connector_id": self.authority.connector_id,
            "credential_ref": self.authority.credential_ref,
            "operations": list(self.authority.operations),
            "read_only": True,
            "credential_contents_exposed": False,
            "remote_mcp_activated": False,
        }


def prepare_agency_read_session(
    envelope: Mapping[str, Any], *,
    pinned_authority_keys: Mapping[str, bytes],
    membership_reader: Callable[[str, str], TenantMembership | None],
    site_grant_reader: Callable[[str, str, str, str], AgencySiteGrant | None],
    trusted_registry_reader: Callable[[str, str, str], CanonicalConnectorBinding | None],
    consume_nonce: Callable[[str], bool],
    trusted_credential_directory: Path,
    trusted_uid: int,
    now: Callable[[], int] | None = None,
) -> SealedAgencyReadSession:
    authority = authorize_agency_connector(
        envelope,
        pinned_authority_keys=pinned_authority_keys,
        membership_reader=membership_reader,
        site_grant_reader=site_grant_reader,
        consume_nonce=consume_nonce,
        now=now,
    )
    if not callable(trusted_registry_reader):
        raise ValueError("Trusted canonical connector registry required")
    try:
        binding = trusted_registry_reader(
            authority.tenant_id, authority.site_id, authority.connector_id)
        if (not isinstance(binding, CanonicalConnectorBinding)
                or binding.active is not True or binding.read_only is not True
                or binding.tenant_id != authority.tenant_id
                or binding.site_id != authority.site_id
                or binding.connector_id != authority.connector_id
                or binding.credential_ref != authority.credential_ref
                or binding.wp_origin != authority.wp_origin
                or binding.allowed_operations != authority.operations):
            raise ValueError()
    except Exception:
        raise ValueError("Canonical connector registry unverified or revoked") from None

    # Credential filename comes from signed authority, fresh site grant AND
    # separately trusted registry; no raw path or agent-provided data accepted.
    password = read_private_connector_password(
        trusted_directory=trusted_credential_directory,
        credential_ref=authority.credential_ref,
        trusted_uid=trusted_uid,
    )
    return SealedAgencyReadSession(authority=authority, _application_password=password)


def revalidate_agency_read_operation(
    session: SealedAgencyReadSession, operation: str, *,
    membership_reader: Callable[[str, str], TenantMembership | None],
    site_grant_reader: Callable[[str, str, str, str], AgencySiteGrant | None],
    trusted_registry_reader: Callable[[str, str, str], CanonicalConnectorBinding | None],
    trusted_credential_directory: Path,
    trusted_uid: int,
    now: Callable[[], int] | None = None,
) -> bool:
    """Recheck CURRENT tenant/site/registry/secret at each MCP tool invocation.

    The short-lived one-time signed envelope is verified at session creation,
    never reused as a fresh grant. This function checks revocation every call
    and never accepts a caller-supplied membership or site grant as proof.
    """
    if not isinstance(session, SealedAgencyReadSession) or not isinstance(operation, str):
        raise ValueError("Signed agency session required")
    a = session.authority
    if operation not in a.operations or operation not in ("capabilities:read", "vehicles:read"):
        raise ValueError("Agency operation denied")
    if int((now or time.time)()) >= a.expires_at:
        raise ValueError("Agency session expired")
    try:
        membership = membership_reader(a.user_id, a.tenant_id)
        if (not isinstance(membership, TenantMembership)
                or membership.user_id != a.user_id
                or membership.tenant_id != a.tenant_id
                or membership.role not in ("owner", "admin")
                or not authorize_tenant_resource(
                    membership=membership,
                    resource=TenantResourceRef(
                        tenant_id=a.tenant_id,
                        resource_type="agency_wordpress_site",
                        resource_id=a.site_id,
                    ),
                    permission="read",
                ).allowed):
            raise ValueError()
        grant = site_grant_reader(a.user_id, a.tenant_id, a.site_id, a.connector_id)
        if (not isinstance(grant, AgencySiteGrant)
                or grant.status != "active"
                or grant.user_id != a.user_id or grant.tenant_id != a.tenant_id
                or grant.site_id != a.site_id or grant.connector_id != a.connector_id
                or grant.credential_ref != a.credential_ref
                or grant.wp_origin != a.wp_origin
                or grant.operations != a.operations):
            raise ValueError()
        binding = trusted_registry_reader(a.tenant_id, a.site_id, a.connector_id)
        if (not isinstance(binding, CanonicalConnectorBinding)
                or binding.active is not True or binding.read_only is not True
                or binding.tenant_id != a.tenant_id or binding.site_id != a.site_id
                or binding.connector_id != a.connector_id
                or binding.credential_ref != a.credential_ref
                or binding.wp_origin != a.wp_origin
                or binding.allowed_operations != a.operations):
            raise ValueError()
        current = read_private_connector_password(
            trusted_directory=trusted_credential_directory,
            credential_ref=a.credential_ref,
            trusted_uid=trusted_uid,
        )
        if not hmac.compare_digest(current, session._application_password):
            raise ValueError()
    except Exception:
        raise ValueError("Agency membership, site, connector or credential revoked") from None
    return True
