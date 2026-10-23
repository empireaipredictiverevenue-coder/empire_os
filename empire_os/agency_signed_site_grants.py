"""Owner-signed, per-site agency connector snapshots; PREPARED ONLY.

Bridges already-verified tenant membership with distinct site-owner and
connector-security approvals. This is an OPTIONAL read-only trust adapter,
not a canonical live site-grant table or a self-service signing authority.

A future authorised owner must install the public keys and maintain snapshots
independently. No signature, site permission or trusted issuer is invented.
"""
from __future__ import annotations

import json
import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.agency_connector_authority import AgencySiteGrant, OPERATIONS, _decode
from empire_os.agency_connector_preflight import CanonicalConnectorBinding

MAX_FILE_BYTES = 8192
MAX_RECORD_LIFETIME = 86400
SITE_SCHEMA = "empire.agency.site-owner-grant.v1"
CONNECTOR_SCHEMA = "empire.agency.connector-security-grant.v1"
SITE_DOMAIN = b"empire-agency-site-owner-grant-v1:"
CONNECTOR_DOMAIN = b"empire-agency-connector-security-grant-v1:"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,95}$")
_SUB = re.compile(r"^[A-Za-z0-9:@._/-]{3,128}$")
_LOOPBACK = re.compile(r"^http://127[.]0[.]0[.]1:([1-9][0-9]{1,4})$")

SITE_FIELDS = frozenset((
    "schema", "issuer", "subject", "tenant_id", "site_id", "connector_id",
    "credential_ref", "wp_origin", "operations", "status", "issued_at",
    "not_before", "expires_at",
))
CONNECTOR_FIELDS = frozenset((
    "schema", "issuer", "tenant_id", "site_id", "connector_id",
    "credential_ref", "wp_origin", "operations", "status", "read_only",
    "issued_at", "not_before", "expires_at",
))


def _load_owner_private_file(path: Path, *, uid: int) -> bytes:
    """Read bounded, regular owner-private file, refusing swapped inode and symlinks."""
    if not isinstance(path, Path) or not path.is_absolute() or type(uid) is not int:
        raise ValueError("Trusted agency grant file identity required")
    try:
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid
                or parent.st_mode & 0o077):
            raise ValueError()
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid
                or st.st_mode & 0o077 or not 32 <= st.st_size <= MAX_FILE_BYTES):
            raise ValueError()
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            check = os.fstat(fd)
            if ((st.st_dev, st.st_ino) != (check.st_dev, check.st_ino)
                    or check.st_uid != uid or check.st_mode & 0o077
                    or not stat.S_ISREG(check.st_mode)):
                raise ValueError()
            data = os.read(fd, MAX_FILE_BYTES + 1)
        finally:
            os.close(fd)
        if len(data) != st.st_size:
            raise ValueError()
        return data
    except (OSError, ValueError):
        raise ValueError("Agency trust snapshot missing or unsafe") from None


def _verified_claims(
    *, path: Path, uid: int, public_keys: Mapping[str, bytes],
    schema: str, fields: frozenset[str], domain: bytes, issuer: str,
    now: Callable[[], int],
) -> dict[str, Any]:
    if not isinstance(public_keys, Mapping) or not public_keys:
        raise ValueError("Pinned agency owner authority required")
    try:
        envelope = json.loads(_load_owner_private_file(path, uid=uid))
        if (not isinstance(envelope, dict)
                or set(envelope) != {"key_id", "claims", "signature"}
                or not isinstance(envelope["claims"], dict)
                or set(envelope["claims"]) != fields):
            raise ValueError()
        kid = envelope["key_id"]
        if not isinstance(kid, str) or not _ID.fullmatch(kid):
            raise ValueError()
        public_key = public_keys.get(kid)
        if not isinstance(public_key, bytes) or len(public_key) != 32:
            raise ValueError()
        payload = envelope["claims"]
        raw = domain + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError()
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            _decode(envelope["signature"], 64), raw,
        )
        if payload["schema"] != schema or payload["issuer"] != issuer:
            raise ValueError()
        if any(type(payload[k]) is not int for k in ("issued_at", "not_before", "expires_at")):
            raise ValueError()
        current = int(now())
        if (payload["issued_at"] > current + 15
                or payload["not_before"] > current
                or payload["expires_at"] <= current
                or payload["expires_at"] <= payload["issued_at"]
                or payload["expires_at"] - payload["issued_at"] > MAX_RECORD_LIFETIME):
            raise ValueError()
        tenant = str(UUID(payload["tenant_id"]))
        if payload["tenant_id"] != tenant:
            raise ValueError()
        if any(not isinstance(payload[k], str) or not _ID.fullmatch(payload[k])
               for k in ("site_id", "connector_id", "credential_ref")):
            raise ValueError()
        matched = _LOOPBACK.fullmatch(payload["wp_origin"])
        if matched is None or not 1 <= int(matched.group(1)) <= 65535:
            raise ValueError()
        if (payload["status"] != "active"
                or type(payload["operations"]) is not list
                or payload["operations"] != list(OPERATIONS)):
            raise ValueError()
        if schema == SITE_SCHEMA and (
                not isinstance(payload["subject"], str)
                or not _SUB.fullmatch(payload["subject"])):
            raise ValueError()
        if schema == CONNECTOR_SCHEMA and payload["read_only"] is not True:
            raise ValueError()
        return payload
    except Exception:
        raise ValueError("Agency owner/security grant missing, invalid or expired") from None


@dataclass(frozen=True)
class SignedAgencySiteSnapshotReader:
    """Requires an already owner-provisioned, pinned site-grant signing key."""
    path: Path
    trusted_uid: int
    site_owner_public_keys: Mapping[str, bytes]
    now: Callable[[], int] = time.time

    def __call__(
        self, subject: str, tenant_id: str, site_id: str, connector_id: str,
    ) -> AgencySiteGrant | None:
        try:
            p = _verified_claims(
                path=self.path, uid=self.trusted_uid,
                public_keys=self.site_owner_public_keys, schema=SITE_SCHEMA,
                fields=SITE_FIELDS, domain=SITE_DOMAIN,
                issuer="empire-agency-site-owner", now=self.now,
            )
            if (p["subject"], p["tenant_id"], p["site_id"], p["connector_id"]) != (
                    subject, tenant_id, site_id, connector_id):
                return None
            return AgencySiteGrant(
                user_id=p["subject"], tenant_id=p["tenant_id"], site_id=p["site_id"],
                connector_id=p["connector_id"], credential_ref=p["credential_ref"],
                wp_origin=p["wp_origin"], status=p["status"],
                operations=OPERATIONS,
            )
        except ValueError:
            return None


@dataclass(frozen=True)
class SignedAgencyConnectorSnapshotReader:
    """Separately signed connector security authorisation, re-read per request."""
    path: Path
    trusted_uid: int
    security_public_keys: Mapping[str, bytes]
    now: Callable[[], int] = time.time

    def __call__(
        self, tenant_id: str, site_id: str, connector_id: str,
    ) -> CanonicalConnectorBinding | None:
        try:
            p = _verified_claims(
                path=self.path, uid=self.trusted_uid,
                public_keys=self.security_public_keys, schema=CONNECTOR_SCHEMA,
                fields=CONNECTOR_FIELDS, domain=CONNECTOR_DOMAIN,
                issuer="empire-agency-connector-security", now=self.now,
            )
            if (p["tenant_id"], p["site_id"], p["connector_id"]) != (
                    tenant_id, site_id, connector_id):
                return None
            return CanonicalConnectorBinding(
                tenant_id=p["tenant_id"], site_id=p["site_id"],
                connector_id=p["connector_id"],
                credential_ref=p["credential_ref"], wp_origin=p["wp_origin"],
                allowed_operations=OPERATIONS, active=True, read_only=True,
            )
        except ValueError:
            return None
