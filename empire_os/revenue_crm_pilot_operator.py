"""Offline, founder-gated CRM pilot invitation provisioning. No HTTP route.

This stores only an already prepared one-use invitation hash after an independent
operator has verified both the real recipient and a current EmpireDB membership.
It does not grant roles, issue tenant memberships, send email or activate CRM.
Execution in production requires separate founder approval and an authorised
local database operator session. Never print or log invitation tokens.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from psycopg.conninfo import conninfo_to_dict

from empire_os.revenue_crm_first_party_login import (
    INVITATION_SECONDS, PreparedCrmInvitation, _INVITATION,
    _SUBJECT, _normal_email,
)

_APPROVAL = re.compile(r"^founder:[A-Za-z0-9._:/-]{12,150}$")
_EMAIL_PROOF = re.compile(r"^verified-email:[A-Za-z0-9._:/-]{12,180}$")


class PostgresCrmInviteOperator:
    """Privileged *offline* provisioning for a single pre-approved pilot user."""

    def __init__(
        self, dsn: str, *,
        connect_factory: Callable | None = None,
        expected_database: str = "empiredb",
    ) -> None:
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("controlled local operator database connection required")
        if expected_database not in {"empiredb", "crm_membership_fixture"}:
            raise ValueError("unsupported CRM provisioning database")
        try:
            info = conninfo_to_dict(dsn)
        except Exception as exc:
            raise ValueError("invalid local operator database connection") from None
        if (
            info.get("dbname") != expected_database
            or info.get("user") != "postgres"
            or not info.get("host", "").startswith("/")
            or any(name in info for name in ("service", "options", "passfile", "hostaddr"))
            or (expected_database == "empiredb" and (
                info.get("host") != "/var/run/postgresql"
                or info.get("port") != "5432"
            ))
        ):
            raise ValueError("local canonical superuser operator DSN required")
        self._dsn = dsn
        self._database = expected_database
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def provision(
        self,
        invitation: PreparedCrmInvitation, *,
        founder_approval_ref: str,
        verified_recipient_ref: str,
    ) -> bool:
        """Insert one pending account, never an active account or membership.

        Preconditions are checked *inside* one DB transaction against a
        current canonical membership row. Existing subjects/emails must NOT
        be overwritten; any failure rolls the transaction back.
        """
        if (
            not isinstance(invitation, PreparedCrmInvitation)
            or not isinstance(founder_approval_ref, str)
            or not _APPROVAL.fullmatch(founder_approval_ref)
            or not isinstance(verified_recipient_ref, str)
            or not _EMAIL_PROOF.fullmatch(verified_recipient_ref)
            or not isinstance(invitation.subject, str)
            or not _SUBJECT.fullmatch(invitation.subject)
            or _normal_email(invitation.login_email) != invitation.login_email
            or not isinstance(invitation.token, str)
            or not _INVITATION.fullmatch(invitation.token)
        ):
            return False
        try:
            tenant = str(UUID(invitation.invitation_tenant_id))
            if tenant != invitation.invitation_tenant_id:
                return False
            digest = hashlib.sha256(invitation.token.encode("ascii")).digest()
            if not (
                isinstance(invitation.invitation_token_hash, bytes)
                and hmac.compare_digest(digest, invitation.invitation_token_hash)
                and isinstance(invitation.password_salt, bytes)
                and len(invitation.password_salt) == 32
                and isinstance(invitation.password_digest, bytes)
                and len(invitation.password_digest) == 64
                and isinstance(invitation.evidence_ref, str)
                and 1 <= len(invitation.evidence_ref.strip()) <= 512
            ):
                return False
            expiry = invitation.expires_at
            if not isinstance(expiry, datetime) or expiry.tzinfo is None:
                return False
            now = datetime.now(timezone.utc)
            remaining = (expiry.astimezone(timezone.utc) - now).total_seconds()
            if remaining <= 0 or remaining > INVITATION_SECONDS + 120:
                return False
        except (TypeError, ValueError, AttributeError):
            return False

        # Store all independently reviewed evidence in the existing 042
        # evidence_ref column; never discard the approval/recipient proofs.
        evidence = (
            f"{invitation.evidence_ref.strip()}|"
            f"{founder_approval_ref}|{verified_recipient_ref}"
        )
        if len(evidence) > 512:
            return False
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='5000ms'")
                    cur.execute("SELECT current_database(), session_user")
                    principal = cur.fetchone()
                    # Privileged, local, manually authorised operator only.
                    if principal != (self._database, "postgres"):
                        return False
                    cur.execute(
                        "SELECT role,status,verified_at,revoked_at,valid_until "
                        "FROM public.empire_crm_tenant_memberships "
                        "WHERE tenant_id=%s::uuid AND subject=%s FOR SHARE",
                        (tenant, invitation.subject),
                    )
                    member = cur.fetchone()
                    if (
                        not isinstance(member, (tuple, list))
                        or len(member) != 5
                        or member[0] not in {"owner","admin","operator","analyst","viewer"}
                        or member[1] != "active"
                        or member[2] is None or member[2] > now
                        or member[3] is not None
                        or (member[4] is not None and member[4] <= now)
                    ):
                        return False
                    cur.execute(
                        "INSERT INTO public.empire_crm_login_credentials "
                        "(subject, login_email, password_salt, password_digest, "
                        "status, evidence_ref, password_change_required, "
                        "verified_at, invitation_tenant_id, invitation_token_hash, "
                        "invitation_expires_at) VALUES "
                        "(%s,%s,%s,%s,'pending',%s,true,clock_timestamp(),"
                        "%s::uuid,%s,%s) "
                        "ON CONFLICT DO NOTHING RETURNING subject",
                        (
                            invitation.subject, invitation.login_email,
                            invitation.password_salt, invitation.password_digest,
                            evidence, tenant,
                            invitation.invitation_token_hash, expiry,
                        ),
                    )
                    result = cur.fetchone()
                    # Duplicate provision is never treated as a successful resend.
                    if result != (invitation.subject,):
                        return False
                    # No token/password is stored. Immutable invite approval
                    # and recipient verification references remain in evidence_ref.
                    return True
        except Exception:
            return False
