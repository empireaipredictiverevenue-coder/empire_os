"""EmpireOS native, invite-only CRM login; NOT mounted until provisioned.

An operator verifies and provisions a real person in canonical EmpireDB before
this opt-in route may accept credentials. This is NOT public self-signup.
Dedicated auth PostgreSQL LOGIN; strict session_user, row lock, scrypt hash,
DB lockout. A valid login still needs live tenant membership in EmpireDB 041.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
import json
import re
import secrets
import time
from collections.abc import Callable
from datetime import datetime, timezone, timedelta
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from empire_os.revenue_crm_signed_auth import (
    AUTHORIZATION_AUDIENCE, AUTHORIZATION_ISSUER, AUTHORIZATION_SCOPE,
)
from empire_os.saas_scale import TenantMembership

LOGIN_ROLE = "empire_crm_auth_login"
SALT_BYTES = 32
DERIVED_BYTES = 64
MIN_PASSWORD_LENGTH = 14
MAX_PASSWORD_LENGTH = 256
# Standard scrypt, ~32MiB working memory, bounded service-side DB lockout.
SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MEMORY = 96 * 1024 * 1024
MAX_FAILURES = 5
TOKEN_SECONDS = 300
INVITATION_SECONDS = 48 * 3600
_INVITATION = re.compile(r"^EI1_[A-Za-z0-9_-]{43}$")

# Prevent cheap username enumeration even for non-existent accounts.
_DUMMY_SALT = hashlib.sha256(b"empire-first-party-unknown-credential").digest()
_SUBJECT = re.compile(r"^[A-Za-z0-9:@._/-]{1,128}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_SELECT = """
SELECT subject,password_salt,password_digest,status,password_change_required,
       failed_attempts,locked_until,verified_at
FROM public.empire_crm_login_credentials
WHERE login_email=%s FOR UPDATE
"""
_FAILURE = """
UPDATE public.empire_crm_login_credentials
SET failed_attempts=LEAST(5,failed_attempts+1),
    locked_until=CASE WHEN failed_attempts>=4
        THEN clock_timestamp()+interval '15 minutes'
        ELSE locked_until END,
    updated_at=clock_timestamp()
WHERE subject=%s
"""
_SUCCESS = """
UPDATE public.empire_crm_login_credentials
SET failed_attempts=0,locked_until=NULL,last_login_at=clock_timestamp(),
    updated_at=clock_timestamp()
WHERE subject=%s
"""


def hash_invited_password(password: str, salt: bytes) -> bytes:
    """Used by an approved *offline* account bootstrap; never log the result."""
    if not isinstance(password, str):
        raise ValueError("CRM password must be text")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError("CRM password length invalid")
    if not isinstance(salt, bytes) or len(salt) != SALT_BYTES:
        raise ValueError("CRM password salt invalid")
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
        p=SCRYPT_P, dklen=DERIVED_BYTES, maxmem=SCRYPT_MEMORY,
    )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _normal_email(login_email: str) -> str | None:
    if not isinstance(login_email, str) or len(login_email) > 254:
        return None
    normalized = login_email.strip().lower()
    if not _EMAIL.fullmatch(normalized):
        return None
    return normalized


@dataclass(frozen=True)
class PreparedCrmInvitation:
    """Operator-only provisioning packet; token must never enter logs/audit."""
    subject: str
    login_email: str
    invitation_tenant_id: str
    token: str
    invitation_token_hash: bytes
    password_salt: bytes
    password_digest: bytes
    evidence_ref: str
    expires_at: datetime


def prepare_crm_invitation(
    *, subject: str, email: str, tenant_id: str, evidence_ref: str,
    now: datetime | None = None,
) -> PreparedCrmInvitation:
    """Construct pending invite material. DOES NOT insert rows or send email.

    Only a separately authorised operator may store the hash/evidence in
    EmpireDB and send the one-time token to the independently verified inbox.
    """
    normalized = _normal_email(email)
    if (
        not isinstance(subject, str) or not _SUBJECT.fullmatch(subject)
        or normalized is None or not isinstance(evidence_ref, str)
        or not 1 <= len(evidence_ref.strip()) <= 512
    ):
        raise ValueError("verified CRM invitation identity/evidence required")
    try:
        tenant = str(UUID(str(tenant_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("canonical CRM invite tenant required") from exc
    if tenant != tenant_id:
        raise ValueError("canonical CRM invite tenant required")
    issued = now or datetime.now(timezone.utc)
    if issued.tzinfo is None:
        raise ValueError("timezone-aware invitation clock required")
    issued = issued.astimezone(timezone.utc)
    token = "EI1_" + secrets.token_urlsafe(32)
    return PreparedCrmInvitation(
        subject=subject, login_email=normalized,
        invitation_tenant_id=tenant, token=token,
        invitation_token_hash=hashlib.sha256(token.encode("ascii")).digest(),
        password_salt=secrets.token_bytes(SALT_BYTES),
        password_digest=secrets.token_bytes(DERIVED_BYTES),
        evidence_ref=evidence_ref.strip(),
        expires_at=issued + timedelta(seconds=INVITATION_SECONDS),
    )


class PostgresCrmPasswordLogin:
    """Dedicated auth LOGIN: does not create accounts, grant roles or send mail."""

    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        self._dsn = str(dsn or "").strip()
        if not self._dsn:
            raise ValueError("dedicated CRM account-login database connection required")
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def authenticate(self, email: str, password: str) -> str | None:
        normalized = _normal_email(email)
        if normalized is None or not isinstance(password, str):
            return None
        if len(password) > MAX_PASSWORD_LENGTH or not password:
            return None
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                    cursor.execute("SELECT session_user")
                    identity = cursor.fetchone()
                    if identity != (LOGIN_ROLE,):
                        return None
                    cursor.execute(_SELECT, (normalized,))
                    row = cursor.fetchone()
                    if row is None:
                        # Bound CPU work regardless of whether email is known.
                        hash_invited_password(
                            password if len(password) >= MIN_PASSWORD_LENGTH
                            else "X" * MIN_PASSWORD_LENGTH,
                            _DUMMY_SALT,
                        )
                        return None
                    if len(row) != 8:
                        return None
                    subject, salt, digest, status, change_required, fails, locked, verified = row
                    if (
                        not isinstance(subject, str) or not _SUBJECT.fullmatch(subject)
                        or not isinstance(salt, (bytes, memoryview)) or len(salt) != SALT_BYTES
                        or not isinstance(digest, (bytes, memoryview)) or len(digest) != DERIVED_BYTES
                    ):
                        return None
                    # Do not accept pending / locked / unverified credentials.
                    now = datetime.now(timezone.utc)
                    if (
                        status != "active" or change_required is not False
                        or verified is None or verified > now
                        or (locked is not None and locked > now)
                        or (int(fails) >= MAX_FAILURES and locked is None)
                    ):
                        return None
                    try:
                        candidate = hash_invited_password(
                            password if len(password) >= MIN_PASSWORD_LENGTH
                            else "X" * MIN_PASSWORD_LENGTH, bytes(salt),
                        )
                    except ValueError:
                        return None
                    matched = (
                        len(password) >= MIN_PASSWORD_LENGTH
                        and hmac.compare_digest(candidate, bytes(digest))
                    )
                    if not matched:
                        cursor.execute(_FAILURE, (subject,))
                        return None
                    cursor.execute(_SUCCESS, (subject,))
                    return subject
        except Exception:
            # Do not expose existence, login names or driver DSN diagnostics.
            return None



    def accept_invitation(
        self, token: str, new_password: str, tenant_id: str,
        *, load_membership: Callable[[str, str], TenantMembership | None],
    ) -> bool:
        """One-time invite redemption; must be delivered via verified email.

        The account is already founder-provisioned and is still pending.
        This endpoint cannot insert accounts, tenants, or membership records.
        """
        if (
            not isinstance(token, str) or not _INVITATION.fullmatch(token)
            or not isinstance(new_password, str)
            or not MIN_PASSWORD_LENGTH <= len(new_password) <= MAX_PASSWORD_LENGTH
            or not callable(load_membership)
        ):
            return False
        try:
            tenant = str(UUID(str(tenant_id)))
        except (TypeError, ValueError, AttributeError):
            return False
        if tenant != tenant_id:
            return False
        invite_digest = hashlib.sha256(token.encode("ascii")).digest()
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '7000ms'")
                    cursor.execute("SELECT session_user")
                    if cursor.fetchone() != (LOGIN_ROLE,):
                        return False
                    cursor.execute(
                        "SELECT subject,status,invitation_expires_at,"
                        "invitation_redeemed_at,verified_at,invitation_tenant_id "
                        "FROM public.empire_crm_login_credentials "
                        "WHERE invitation_token_hash=%s FOR UPDATE",
                        (invite_digest,),
                    )
                    row = cursor.fetchone()
                    if not isinstance(row, (tuple, list)) or len(row) != 6:
                        return False
                    subject, status, expires, redeemed, verified, invited_tenant = row
                    now = datetime.now(timezone.utc)
                    if (
                        not isinstance(subject, str) or not _SUBJECT.fullmatch(subject)
                        or status != "pending" or redeemed is not None
                        or str(invited_tenant) != tenant
                        or expires is None or expires <= now
                        or verified is None or verified > now
                    ):
                        return False
                    try:
                        membership = load_membership(subject, tenant)
                        permitted = (
                            isinstance(membership, TenantMembership)
                            and membership.user_id == subject
                            and membership.tenant_id == tenant
                            and membership.can("read")
                        )
                    except Exception:
                        permitted = False
                    if not permitted:
                        return False
                    salt = secrets.token_bytes(SALT_BYTES)
                    digest = hash_invited_password(new_password, salt)
                    cursor.execute(
                        "UPDATE public.empire_crm_login_credentials SET "
                        "password_salt=%s,password_digest=%s,"
                        "status='active',password_change_required=false,"
                        "invitation_token_hash=NULL,"
                        "invitation_redeemed_at=clock_timestamp(),"
                        "failed_attempts=0,locked_until=NULL,"
                        "updated_at=clock_timestamp() "
                        "WHERE subject=%s AND status='pending' "
                        "AND invitation_token_hash=%s "
                        "AND invitation_tenant_id=%s::uuid "
                        "AND invitation_expires_at>clock_timestamp() "
                        "RETURNING subject",
                        (salt, digest, subject, invite_digest, tenant),
                    )
                    success = cursor.fetchone()
                    return success == (subject,)
        except Exception:
            # Driver failures may contain credentials; no details to caller.
            return False

    def active_account(self, subject: str) -> bool:
        """Fresh, separate read: revoked login blocks previously issued JWTs."""
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            return False
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                    cursor.execute("SELECT session_user")
                    if cursor.fetchone() != (LOGIN_ROLE,):
                        return False
                    cursor.execute(
                        "SELECT status,password_change_required,verified_at "
                        "FROM public.empire_crm_login_credentials WHERE subject=%s",
                        (subject,),
                    )
                    row = cursor.fetchone()
                    return bool(
                        isinstance(row, (tuple, list)) and len(row) == 3
                        and row[0] == "active" and row[1] is False
                        and row[2] is not None
                        and row[2] <= datetime.now(timezone.utc)
                        and cursor.fetchone() is None
                    )
        except Exception:
            return False


def build_account_bound_membership_lookup(
    password_login: PostgresCrmPasswordLogin,
    membership_lookup: Callable[[str, str], TenantMembership | None],
) -> Callable[[str, str], TenantMembership | None]:
    """Use SAME callback for CRM bearer verifier AND the login issuer.

    A disabled account or unavailable credential store revokes existing
    bearer access, even if a five-minute JWT remains cryptographically valid.
    """
    if not isinstance(password_login, PostgresCrmPasswordLogin):
        raise ValueError("trusted first-party CRM account reader required")
    if not callable(membership_lookup):
        raise ValueError("trusted CRM membership reader required")

    def lookup(subject: str, tenant_id: str) -> TenantMembership | None:
        if not password_login.active_account(subject):
            return None
        try:
            membership = membership_lookup(subject, tenant_id)
            if (
                isinstance(membership, TenantMembership)
                and membership.user_id == subject
                and membership.tenant_id == tenant_id
                and membership.can("read")
            ):
                return membership
        except Exception:
            pass
        return None

    return lookup


class CrmLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    tenant_id: str = Field(min_length=36, max_length=36)


class CrmInviteAcceptRequest(BaseModel):
    invitation_token: str = Field(min_length=45, max_length=64)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    tenant_id: str = Field(min_length=36, max_length=36)


def _verified_member(
    load_membership: Callable[[str, str], TenantMembership | None],
    subject: str, tenant_id: str,
) -> bool:
    try:
        membership = load_membership(subject, tenant_id)
        return bool(
            isinstance(membership, TenantMembership)
            and membership.user_id == subject and membership.tenant_id == tenant_id
            and membership.can("read")
        )
    except Exception:
        return False


def create_crm_login_router(
    *,
    password_login: PostgresCrmPasswordLogin,
    load_membership: Callable[[str, str], TenantMembership | None],
    load_invitation_membership: Callable[[str, str], TenantMembership | None],
    signing_key: Ed25519PrivateKey,
    key_id: str,
    now: Callable[[], int] | None = None,
) -> APIRouter:
    """Opt-in in existing Hub only after independently audited config."""
    if (
        not isinstance(password_login, PostgresCrmPasswordLogin)
        or not callable(load_membership)
        or not callable(load_invitation_membership)
        or not isinstance(signing_key, Ed25519PrivateKey)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key_id or "")
    ):
        raise ValueError("canonical CRM login dependencies required")
    clock = now or (lambda: int(time.time()))
    router = APIRouter(prefix="/v1/revenue-crm/auth", tags=["revenue-crm-auth"])

    @router.post("/accept-invite")
    def accept_invite(request: CrmInviteAcceptRequest, response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not password_login.accept_invitation(
            request.invitation_token, request.new_password, request.tenant_id,
            load_membership=load_invitation_membership,
        ):
            raise HTTPException(status_code=401, detail="crm_invite_denied")
        # Deliberately no auto-login: user signs in after redeeming.
        return {
            "accepted": True,
            "access_token_issued": False,
            "login_required": True,
        }

    @router.post("/login")
    def login(request: CrmLoginRequest, response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        try:
            tenant_id = str(UUID(request.tenant_id))
        except (TypeError, ValueError, AttributeError):
            tenant_id = ""
        if tenant_id != request.tenant_id:
            raise HTTPException(status_code=401, detail="crm_login_denied")
        subject = password_login.authenticate(request.email, request.password)
        if not subject or not _verified_member(load_membership, subject, tenant_id):
            raise HTTPException(status_code=401, detail="crm_login_denied")
        issued = int(clock())
        header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id}
        claims = {
            "iss": AUTHORIZATION_ISSUER, "aud": AUTHORIZATION_AUDIENCE,
            "sub": subject, "tenant_id": tenant_id, "scope": AUTHORIZATION_SCOPE,
            "iat": issued, "nbf": issued, "exp": issued + TOKEN_SECONDS,
            "jti": secrets.token_urlsafe(24),
        }
        signed = (
            _b64url(json.dumps(header, separators=(",", ":")).encode()) + "."
            + _b64url(json.dumps(claims, separators=(",", ":")).encode())
        )
        return {
            "access_token": signed + "." +
                _b64url(signing_key.sign(signed.encode("ascii"))),
            "token_type": "Bearer",
            "expires_in": TOKEN_SECONDS,
            "scope": AUTHORIZATION_SCOPE,
        }

    return router
