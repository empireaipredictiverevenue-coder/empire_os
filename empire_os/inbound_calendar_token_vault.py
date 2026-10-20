"""Encrypted, tenant-owned local Calendar OAuth credential vault.

Development staging backend, NOT the production secret store. No public API
exposes this class. Runtime decryption keys MUST come from an authorised
external KMS/secret manager and NEVER from repo contents or SQLite itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import stat

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from empire_os.inbound_calendar_oauth_boundary import ALLOWED_GOOGLE_READ_SCOPES
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError


def _aware(moment: datetime) -> None:
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise CalendarVerificationError("calendar_credential_timezone_required")


@dataclass(frozen=True)
class CalendarCredential:
    tenant_id: str
    calendar_id: str
    provider_account_ref: str
    google_client_id: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    scopes: frozenset[str] = frozenset()
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    customer_approved: bool = False
    provider_grant_verified: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "calendar_id", "provider_account_ref", "google_client_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 250:
                raise CalendarVerificationError("invalid_calendar_credential_identity")
        for token in (self.access_token, self.refresh_token):
            if not isinstance(token, str) or not token.strip() or len(token) > 8192:
                raise CalendarVerificationError("invalid_oauth_credential_material")
        if not isinstance(self.scopes, frozenset) or not self.scopes or not self.scopes <= ALLOWED_GOOGLE_READ_SCOPES:
            raise CalendarVerificationError("calendar_credential_scopes_not_readonly")
        _aware(self.issued_at)
        _aware(self.expires_at)
        if self.expires_at <= self.issued_at or self.expires_at - self.issued_at > timedelta(hours=1):
            raise CalendarVerificationError("invalid_calendar_credential_lifetime")
        if not self.customer_approved or not self.provider_grant_verified:
            raise CalendarVerificationError("calendar_credential_approval_missing")


class OfflineCalendarCredentialVault:
    """Staging-only encrypted SQLite storage, no OAuth key generation or network.

    A new on-disk vault is created mode 0600; an existing one is required to be
    an ordinary owner-restricted file. No method creates a Google credential.
    """

    def __init__(self, path: str | Path, *, active_key: bytes, previous_keys: tuple[bytes, ...] = ()):
        self.path = Path(path)
        if self.path != Path(":memory:"):
            if not self.path.is_absolute() or self.path.is_symlink() or not self.path.parent.is_dir():
                raise CalendarVerificationError("private_calendar_vault_path_required")
            if not self.path.exists():
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            mode = self.path.stat().st_mode
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
                raise CalendarVerificationError("calendar_vault_must_be_owner_only_0600")
        try:
            self._keys = MultiFernet([Fernet(key) for key in (active_key, *previous_keys)])
        except (ValueError, TypeError) as exc:
            raise CalendarVerificationError("invalid_calendar_vault_key") from exc
        self.db = sqlite3.connect(str(self.path), timeout=3)
        self.db.execute("PRAGMA busy_timeout=3000")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS calendar_oauth_credentials (
                calendar_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                provider_account_ref TEXT NOT NULL,
                encrypted_credentials BLOB NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','revoked')),
                last_updated_at TEXT NOT NULL
            )
        """)
        self.db.commit()

    def __enter__(self) -> "OfflineCalendarCredentialVault":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    @staticmethod
    def _to_json(credential: CalendarCredential) -> bytes:
        return json.dumps({
            "tenant_id": credential.tenant_id,
            "calendar_id": credential.calendar_id,
            "provider_account_ref": credential.provider_account_ref,
            "google_client_id": credential.google_client_id,
            "access_token": credential.access_token,
            "refresh_token": credential.refresh_token,
            "scopes": sorted(credential.scopes),
            "issued_at": credential.issued_at.isoformat(),
            "expires_at": credential.expires_at.isoformat(),
            "customer_approved": credential.customer_approved,
            "provider_grant_verified": credential.provider_grant_verified,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _from_json(blob: bytes) -> CalendarCredential:
        try:
            doc = json.loads(blob)
            if not isinstance(doc, dict):
                raise ValueError("not_object")
            return CalendarCredential(
                tenant_id=doc["tenant_id"],
                calendar_id=doc["calendar_id"],
                provider_account_ref=doc["provider_account_ref"],
                google_client_id=doc["google_client_id"],
                access_token=doc["access_token"],
                refresh_token=doc["refresh_token"],
                scopes=frozenset(doc["scopes"]),
                issued_at=datetime.fromisoformat(doc["issued_at"]),
                expires_at=datetime.fromisoformat(doc["expires_at"]),
                customer_approved=doc["customer_approved"],
                provider_grant_verified=doc["provider_grant_verified"],
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise CalendarVerificationError("invalid_calendar_vault_payload") from exc

    def put_verified_offline(self, credential: CalendarCredential, *, at: datetime) -> None:
        _aware(at)
        encrypted = self._keys.encrypt(self._to_json(credential))
        with self.db:
            prior = self.db.execute(
                "SELECT tenant_id,provider_account_ref,status FROM calendar_oauth_credentials "
                "WHERE calendar_id=?", (credential.calendar_id,),
            ).fetchone()
            if prior is not None:
                if prior[:2] != (credential.tenant_id, credential.provider_account_ref):
                    raise CalendarVerificationError("calendar_vault_cross_tenant_overwrite_denied")
                if prior[2] != "active":
                    raise CalendarVerificationError("revoked_calendar_requires_new_explicit_onboarding")
            self.db.execute(
                "INSERT INTO calendar_oauth_credentials "
                "(calendar_id,tenant_id,provider_account_ref,encrypted_credentials,last_updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(calendar_id) DO UPDATE SET "
                "encrypted_credentials=excluded.encrypted_credentials,"
                "last_updated_at=excluded.last_updated_at",
                (credential.calendar_id, credential.tenant_id,
                 credential.provider_account_ref, encrypted, at.isoformat()),
            )

    def get_active(
        self, *, tenant_id: str, calendar_id: str, provider_account_ref: str,
    ) -> CalendarCredential:
        row = self.db.execute(
            "SELECT encrypted_credentials,status FROM calendar_oauth_credentials "
            "WHERE tenant_id=? AND calendar_id=? AND provider_account_ref=?",
            (tenant_id, calendar_id, provider_account_ref),
        ).fetchone()
        if row is None or row[1] != "active":
            raise CalendarVerificationError("calendar_credential_not_active_or_not_owned")
        try:
            credential = self._from_json(self._keys.decrypt(row[0]))
        except InvalidToken as exc:
            raise CalendarVerificationError("calendar_credential_decryption_failed") from exc
        if (credential.tenant_id, credential.calendar_id, credential.provider_account_ref) != (
            tenant_id, calendar_id, provider_account_ref,
        ):
            raise CalendarVerificationError("calendar_vault_integrity_or_tenant_mismatch")
        return credential

    def revoke_local(
        self, *, tenant_id: str, calendar_id: str, provider_account_ref: str,
        at: datetime,
    ) -> bool:
        """Immediate LOCAL suppression. Separate Google revocation is still required."""
        _aware(at)
        with self.db:
            changed = self.db.execute(
                "UPDATE calendar_oauth_credentials SET status='revoked',"
                "encrypted_credentials=x'',last_updated_at=? "
                "WHERE tenant_id=? AND calendar_id=? AND provider_account_ref=? "
                "AND status='active'",
                (at.isoformat(), tenant_id, calendar_id, provider_account_ref),
            ).rowcount
        return bool(changed)

    def rotate_encryption_offline(self) -> int:
        """Rewrap using first key. Previous keys must remain until all rows rotate."""
        rows = self.db.execute(
            "SELECT calendar_id,tenant_id,provider_account_ref,encrypted_credentials "
            "FROM calendar_oauth_credentials WHERE status='active'"
        ).fetchall()
        updated = 0
        with self.db:
            for calendar_id, tenant, account, encrypted in rows:
                try:
                    original = self._from_json(self._keys.decrypt(encrypted))
                except InvalidToken as exc:
                    raise CalendarVerificationError("calendar_key_rotation_failed") from exc
                if (original.calendar_id, original.tenant_id, original.provider_account_ref) != (
                    calendar_id, tenant, account
                ):
                    raise CalendarVerificationError("calendar_rotation_tenant_mismatch")
                new_blob = self._keys.encrypt(self._to_json(original))
                self.db.execute(
                    "UPDATE calendar_oauth_credentials SET encrypted_credentials=? "
                    "WHERE calendar_id=? AND status='active'",
                    (new_blob, calendar_id),
                )
                updated += 1
        return updated

    def status(self, *, tenant_id: str) -> dict:
        rows = self.db.execute(
            "SELECT status,COUNT(*) FROM calendar_oauth_credentials "
            "WHERE tenant_id=? GROUP BY status", (tenant_id,),
        ).fetchall()
        numbers = dict(rows)
        return {
            "tenant_id": tenant_id,
            "active_local_credentials": numbers.get("active", 0),
            "revoked_local_credentials": numbers.get("revoked", 0),
            "exposes_tokens": False,
            "production_vault": False,
        }
