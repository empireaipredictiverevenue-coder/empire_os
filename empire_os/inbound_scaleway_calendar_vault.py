"""Scaleway Secret Manager credential backend, opt-in and per-tenant pinned.

NO secrets, account IDs or billing resources are provisioned on import. Secret
containers MUST be pre-created by the authorised owner and bound to one
tenant/calendar/account key. IAM must enforce access to those exact secrets.
Secret versions contain encrypted-at-rest credential JSON managed by Scaleway.
"""
from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Mapping
from datetime import datetime
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from uuid import UUID

from empire_os.inbound_calendar_token_vault import (
    CalendarCredential, OfflineCalendarCredentialVault, _aware,
)
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError


class CalendarCredentialStore(Protocol):
    def put_verified_offline(self, credential: CalendarCredential, *, at: datetime) -> None: ...
    def get_active(self, *, tenant_id: str, calendar_id: str,
                   provider_account_ref: str) -> CalendarCredential: ...
    def revoke_local(self, *, tenant_id: str, calendar_id: str,
                     provider_account_ref: str, at: datetime) -> bool: ...


class SecretVersionGateway(Protocol):
    def access_latest(self, secret_id: str) -> bytes | None: ...
    def add_version(self, secret_id: str, payload: bytes) -> int: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class ScalewaySecretManagerHTTP:
    """Exact preapproved secret UUIDs, no arbitrary URLs/redirects or logs.

    Every API request obtains a fresh access token from an operator-controlled
    systemd credential or secret manager adapter, never caller input.
    """

    REGIONS = frozenset({"fr-par", "nl-ams", "pl-waw"})

    def __init__(self, *, region: str, api_token: Callable[[], str],
                 timeout_seconds: float = 6):
        if (region not in self.REGIONS or not callable(api_token)
            or not 1 <= timeout_seconds <= 12):
            raise ValueError("scaleway_secret_manager_private_config_required")
        self.prefix = (
            "https://api.scaleway.com/secret-manager/v1beta1/regions/" +
            region + "/secrets/"
        )
        self.token_provider = api_token
        self.timeout = timeout_seconds
        self.opener = build_opener(ProxyHandler({}), _NoRedirect)

    @staticmethod
    def _uuid(value: str) -> str:
        if not isinstance(value, str):
            raise CalendarVerificationError("configured_secret_uuid_required")
        try:
            canonical = str(UUID(value))
        except (ValueError, TypeError, AttributeError):
            raise CalendarVerificationError("configured_secret_uuid_required") from None
        if canonical != value:
            raise CalendarVerificationError("configured_secret_uuid_required")
        return canonical

    def _send(self, secret_id: str, *, path: str, method: str,
              body: bytes | None = None) -> dict | None:
        secret_id = self._uuid(secret_id)
        token = self.token_provider()
        if (not isinstance(token, str) or not 20 <= len(token) <= 1024
            or token != token.strip() or "\n" in token or "\r" in token):
            raise CalendarVerificationError("scaleway_iam_credential_unavailable")
        if path not in ("/versions/latest_enabled/access", "/versions"):
            raise CalendarVerificationError("scaleway_secret_manager_action_not_allowed")
        if (path == "/versions" and method != "POST") or (
            path.endswith("/access") and method != "GET"):
            raise CalendarVerificationError("scaleway_secret_manager_method_not_allowed")
        request = Request(
            self.prefix + secret_id + path, data=body, method=method,
            headers={"X-Auth-Token": token, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise CalendarVerificationError("scaleway_secret_version_not_verified")
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise CalendarVerificationError("scaleway_secret_response_too_large")
                data = json.loads(raw)
        except HTTPError as exc:
            # 404 is allowed ONLY for a not-yet-written pre-provisioned
            # secret. Calls to create version still require successful proof.
            if exc.code == 404 and method == "GET":
                return None
            raise CalendarVerificationError("scaleway_secret_manager_unavailable") from None
        except (URLError, OSError, TimeoutError, ValueError):
            raise CalendarVerificationError("scaleway_secret_manager_unavailable") from None
        if not isinstance(data, dict) or data.get("secret_id") != secret_id:
            raise CalendarVerificationError("scaleway_secret_identity_mismatch")
        return data

    def access_latest(self, secret_id: str) -> bytes | None:
        doc = self._send(
            secret_id, path="/versions/latest_enabled/access", method="GET",
        )
        if doc is None:
            return None
        encoded = doc.get("data")
        if doc.get("type") != "opaque" or not isinstance(encoded, str) or len(encoded) > 50000:
            raise CalendarVerificationError("scaleway_calendar_secret_not_opaque")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise CalendarVerificationError("scaleway_secret_base64_invalid") from None
        if not 1 <= len(raw) <= 32000:
            raise CalendarVerificationError("scaleway_secret_payload_invalid")
        checksum = doc.get("data_crc32")
        if checksum is not None and (
            type(checksum) is not int or not 0 <= checksum <= 0xffffffff
            or checksum != binascii.crc32(raw) & 0xffffffff
        ):
            raise CalendarVerificationError("scaleway_secret_checksum_mismatch")
        return raw

    def add_version(self, secret_id: str, payload: bytes) -> int:
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= 32000:
            raise CalendarVerificationError("scaleway_secret_payload_invalid")
        body = json.dumps({
            "data": base64.b64encode(payload).decode("ascii"),
            "disable_previous": True,
            "data_crc32": binascii.crc32(payload) & 0xffffffff,
        }, separators=(",", ":")).encode("utf-8")
        doc = self._send(secret_id, path="/versions", method="POST", body=body)
        revision = doc.get("revision") if doc else None
        if (type(revision) is not int or revision < 1
            or doc.get("status") != "enabled"):
            raise CalendarVerificationError("scaleway_secret_version_write_unverified")
        return revision


class ScalewaySecretManagerCalendarVault:
    """External IAM/KMS-managed credential storage; no local token database.

    Uses exact, preprovisioned secret UUIDs. Each version is bound to the
    tenant/calendar/provider tuple inside the stored payload, revalidated
    on every read. Single authorised writer per secret is REQUIRED: Scaleway
    secret versions are not a compare-and-swap transaction.
    """

    def __init__(
        self, gateway: SecretVersionGateway,
        *,
        approved_secret_ids: Mapping[tuple[str, str, str], str],
    ):
        if (not callable(getattr(gateway, "access_latest", None))
            or not callable(getattr(gateway, "add_version", None))
            or not isinstance(approved_secret_ids, Mapping)
            or not approved_secret_ids):
            raise ValueError("preprovisioned_secret_manager_binding_required")
        mappings = {}
        seen = set()
        for key, secret_id in approved_secret_ids.items():
            if (not isinstance(key, tuple) or len(key) != 3
                or any(not isinstance(p, str) or not p.strip() or len(p) > 240
                       for p in key)):
                raise ValueError("approved_calendar_secret_identity_required")
            canonical = ScalewaySecretManagerHTTP._uuid(secret_id)
            if canonical in seen:
                raise ValueError("secret_cannot_be_shared_across_calendar_tenants")
            seen.add(canonical)
            mappings[key] = canonical
        self.gateway = gateway
        self.ids = mappings

    def __enter__(self) -> "ScalewaySecretManagerCalendarVault":
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def _id(self, tenant: str, calendar: str, account: str) -> str:
        value = self.ids.get((tenant, calendar, account))
        if value is None:
            raise CalendarVerificationError("calendar_secret_not_preprovisioned_for_tenant")
        return value

    def _read(self, secret_id: str) -> tuple[str, CalendarCredential | None] | None:
        raw = self.gateway.access_latest(secret_id)
        if raw is None:
            return None
        try:
            doc = json.loads(raw)
            if not isinstance(doc, dict) or set(doc) != {"state", "credential"}:
                raise ValueError("invalid secret version shape")
            state = doc["state"]
            if state == "revoked" and doc["credential"] is None:
                return "revoked", None
            if state != "active" or not isinstance(doc["credential"], dict):
                raise ValueError("invalid secret version state")
            credential = OfflineCalendarCredentialVault._from_json(
                json.dumps(doc["credential"], separators=(",", ":")).encode("utf-8")
            )
            return "active", credential
        except (TypeError, ValueError, KeyError, UnicodeError):
            raise CalendarVerificationError("calendar_secret_integrity_failure") from None

    def get_active(self, *, tenant_id: str, calendar_id: str,
                   provider_account_ref: str) -> CalendarCredential:
        secret_id = self._id(tenant_id, calendar_id, provider_account_ref)
        found = self._read(secret_id)
        if found is None or found[0] != "active" or found[1] is None:
            raise CalendarVerificationError("calendar_secret_missing_or_revoked")
        value = found[1]
        if (value.tenant_id, value.calendar_id, value.provider_account_ref) != (
            tenant_id, calendar_id, provider_account_ref
        ):
            raise CalendarVerificationError("calendar_secret_cross_tenant_integrity_failed")
        return value

    def put_verified_offline(self, credential: CalendarCredential, *, at: datetime) -> None:
        # Legacy method name matches the shared credential-store contract,
        # but this implementation DOES call externally configured IAM APIs.
        _aware(at)
        if not isinstance(credential, CalendarCredential):
            raise CalendarVerificationError("verified_calendar_credential_required")
        secret_id = self._id(
            credential.tenant_id, credential.calendar_id,
            credential.provider_account_ref,
        )
        existing = self._read(secret_id)
        if existing is not None:
            if existing[0] == "revoked":
                raise CalendarVerificationError("revoked_calendar_requires_new_consent")
            current = existing[1]
            if (current.tenant_id, current.calendar_id,
                current.provider_account_ref) != (
                    credential.tenant_id, credential.calendar_id,
                    credential.provider_account_ref):
                raise CalendarVerificationError("scaleway_calendar_tenant_conflict")
        payload = json.dumps({
            "state": "active",
            "credential": json.loads(
                OfflineCalendarCredentialVault._to_json(credential)),
        }, separators=(",", ":")).encode()
        self.gateway.add_version(secret_id, payload)
        verified = self._read(secret_id)
        if (verified is None or verified[0] != "active"
            or verified[1] != credential):
            raise CalendarVerificationError("scaleway_calendar_write_readback_not_verified")

    def revoke_local(self, *, tenant_id: str, calendar_id: str,
                     provider_account_ref: str, at: datetime) -> bool:
        # Legacy method name; this is a remote IAM write with previous
        # versions disabled. Provider Google revocation is still separate.
        _aware(at)
        secret_id = self._id(tenant_id, calendar_id, provider_account_ref)
        current = self._read(secret_id)
        if current is None or current[0] == "revoked":
            return False
        if current[1] is None or (
            current[1].tenant_id, current[1].calendar_id,
            current[1].provider_account_ref
        ) != (tenant_id, calendar_id, provider_account_ref):
            raise CalendarVerificationError("scaleway_calendar_revoke_tenant_mismatch")
        payload = b'{"state":"revoked","credential":null}'
        self.gateway.add_version(secret_id, payload)
        after = self._read(secret_id)
        if after is None or after[0] != "revoked" or after[1] is not None:
            raise CalendarVerificationError("scaleway_calendar_revoke_readback_not_verified")
        return True

    def status(self, *, tenant_id: str) -> dict:
        # Avoid reading all customer secrets for a dashboard. Active/revoked
        # needs separate audited provider lookups, never guessed.
        return {
            "tenant_id": tenant_id,
            "backend": "scaleway_secret_manager",
            "known_active_credentials": None,
            "known_revoked_credentials": None,
            "tokens_returned": False,
            "remote_proof_required": True,
        }
