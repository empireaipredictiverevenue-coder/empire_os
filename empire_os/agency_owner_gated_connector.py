"""Owner-gated agency session binding; no production service auto-start.

This is the narrowly typed, fail-closed adapter that will replace the
test-only Python bridge once owners provision approved public keys, live
site authority, and per-client secret delivery. No global DSN or env fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Any

from empire_os.agency_canonical_membership import AgencyCanonicalMembershipReader
from empire_os.agency_connector_preflight import (
    SealedAgencyReadSession, prepare_agency_read_session,
    revalidate_agency_read_operation,
)
from empire_os.agency_private_nonce_store import PrivateAgencyNonceStore
from empire_os.agency_signed_site_grants import (
    SignedAgencySiteSnapshotReader, SignedAgencyConnectorSnapshotReader,
)


@dataclass(frozen=True)
class OwnerGatedAgencyConnector:
    canonical_member: AgencyCanonicalMembershipReader
    site_owner: SignedAgencySiteSnapshotReader
    connector_security: SignedAgencyConnectorSnapshotReader
    replay_receipts: PrivateAgencyNonceStore
    issuer_public_keys: Mapping[str, bytes]
    credential_directory: Path
    trusted_uid: int

    def __post_init__(self) -> None:
        # Refuse arbitrary lambdas, staging JSON, environment-asserted owner
        # strings, and cross-purpose signing keys. The canonical owner supplies
        # issuer keys; this code does not mint grants or promote CRM JWTs.
        if (type(self.canonical_member) is not AgencyCanonicalMembershipReader
                or type(self.site_owner) is not SignedAgencySiteSnapshotReader
                or type(self.connector_security) is not SignedAgencyConnectorSnapshotReader
                or type(self.replay_receipts) is not PrivateAgencyNonceStore
                or not isinstance(self.issuer_public_keys, Mapping)
                or not self.issuer_public_keys or type(self.trusted_uid) is not int
                or self.trusted_uid < 0):
            raise ValueError("Independent owner-provisioned agency trust required")
        key_sets = [
            self.issuer_public_keys,
            self.site_owner.site_owner_public_keys,
            self.connector_security.security_public_keys,
        ]
        if any(not keys for keys in key_sets):
            raise ValueError("All three independent agency signing issuers required")
        key_bytes = []
        for keys in key_sets:
            for value in keys.values():
                if not isinstance(value, bytes) or len(value) != 32:
                    raise ValueError("Pinned Ed25519 public key required")
                key_bytes.append(value)
        if len(key_bytes) != len(set(key_bytes)):
            raise ValueError("Issuer, site owner and security keys must be independent")
        if (self.site_owner.trusted_uid != self.trusted_uid
                or self.connector_security.trusted_uid != self.trusted_uid
                or self.replay_receipts.trusted_uid != self.trusted_uid
                or not isinstance(self.credential_directory, Path)):
            raise ValueError("Owner-provisioned credential and snapshot identity required")

    def open_session(self, signed_envelope: Mapping[str, Any]) -> SealedAgencyReadSession:
        return prepare_agency_read_session(
            signed_envelope,
            pinned_authority_keys=self.issuer_public_keys,
            membership_reader=self.canonical_member,
            site_grant_reader=self.site_owner,
            trusted_registry_reader=self.connector_security,
            consume_nonce=self.replay_receipts,
            trusted_credential_directory=self.credential_directory,
            trusted_uid=self.trusted_uid,
        )

    def authorize_tool(self, session: SealedAgencyReadSession, operation: str) -> bool:
        # No caching or caller-supplied site ownership: re-read current signed
        # snapshots, the live 041 membership and current protected credential.
        return revalidate_agency_read_operation(
            session, operation,
            membership_reader=self.canonical_member,
            site_grant_reader=self.site_owner,
            trusted_registry_reader=self.connector_security,
            trusted_credential_directory=self.credential_directory,
            trusted_uid=self.trusted_uid,
        )
