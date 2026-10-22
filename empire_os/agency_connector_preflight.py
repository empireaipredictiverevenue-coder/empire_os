"""Prepare an agency connector secret only after canonical signed + site authority.

No runtime is launched by this module. Never accept CRM bearer tokens as agency
identity or permit a registry value to mint its own membership/site rights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Any

from empire_os.saas_scale import TenantMembership
from empire_os.agency_connector_authority import (
    AgencySiteGrant, authorize_agency_connector, AuthorizedConnectorRead,
)
from empire_os.agency_connector_credentials import read_private_connector_password


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
