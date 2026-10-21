"""Assemble the original scoped consumer backend in a private process.

Not a server, systemd unit, application router, signup switch, background
job or Resend sender. Importing this module has zero side effects. Every
credential and approval must be explicitly injected by the authorised
private service. The public gateway must NEVER read these secrets.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import re
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

from empire_os.consumer_optin_connection_custody import (
    PrivateConsumerConnectionFactory, LOGIN
)
from empire_os.consumer_optin_postgres_repository import ConsumerPostgresRepository
from empire_os.consumer_optin_private_service import Keys, PrivateConsumerOptinService
from empire_os.consumer_optin_resend_sender import ResendConsumerConfirmationSender
from empire_os.consumer_optin_suppression_reader import ConsumerPrivateSuppressionReader

SECRET = re.compile(r"[a-f0-9]{64}\Z")


class LiveReadbackConsumerRepository(ConsumerPostgresRepository):
    """Status and write readiness require a fresh original private DB session."""

    def _fresh_private_session(self) -> bool:
        if not self._approved:
            return False
        try:
            with self._connect() as conn:
                # ConnectionFactory checks the effective scoped role,
                # memberships, table ACLs and all five RLS policies.
                return conn.execute(
                    "SELECT current_user=%s AND current_database()='empiredb'",
                    ("empire_consumer_optin_writer",),
                ).fetchone() == (True,)
        except Exception:
            return False

    def signup_writable(self) -> bool:
        return self._fresh_private_session()

    def token_processing_writable(self) -> bool:
        # Withdrawals must keep working even if the sender is paused.
        return self._fresh_private_session()


@dataclass(frozen=True,repr=False)
class PrivateConsumerCredentialMaterial:
    """Securely delegated credential bytes, not read from environment here."""
    db_password: str
    email_hmac: bytes
    token_hmac: bytes
    email_encryption: bytes
    key_reference: str

    def __post_init__(self) -> None:
        if (not isinstance(self.db_password,str)
            or SECRET.fullmatch(self.db_password) is None):
            raise ValueError("PRIVATE_DB_LOGIN_PASSWORD_CUSTODY_REQUIRED")
        Keys(
            email_hmac=self.email_hmac,
            token_hmac=self.token_hmac,
            email_encryption=self.email_encryption,
            email_key_reference=self.key_reference,
        ).validate()

    @classmethod
    def from_delegated_secret_parts(cls, *, pgpass: bytes,
                                    key_document: bytes):
        """Parse restricted service credentials provided by its private OS owner.

        Nothing is read from a path, global DB configuration or environment.
        Do not pass direct output of an exposed public web request.
        """
        import json
        try:
            lines=pgpass.decode("ascii").splitlines()
            if len(lines)!=1:
                raise ValueError
            host, port, db, user, password = lines[0].split(":")
            if (host,port,db,user)!=("127.0.0.1","5432","empiredb",LOGIN):
                raise ValueError
            info=json.loads(key_document)
            if not isinstance(info,dict) or set(info)!={
                "email_hmac","token_hmac","email_encryption","key_reference"
            }:
                raise ValueError
            return cls(
                db_password=password,
                email_hmac=bytes.fromhex(info["email_hmac"]),
                token_hmac=bytes.fromhex(info["token_hmac"]),
                email_encryption=bytes.fromhex(info["email_encryption"]),
                key_reference=info["key_reference"],
            )
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("INVALID_DELEGATED_PRIVATE_CONSUMER_CREDENTIALS") from None

    def __repr__(self) -> str:
        return "PrivateConsumerCredentialMaterial(<redacted>)"


def build_private_consumer_backend(
    *,
    material: PrivateConsumerCredentialMaterial,
    owner_approved_private_custody: bool = False,
    owner_approved_confirmation_send: bool = False,
    sender_domain_independently_verified: bool = False,
    resend_scoped_key: str | None = None,
    db_connect: Callable[..., Any] = psycopg.connect,
    resend_provider: Callable | None = None,
) -> PrivateConsumerOptinService:
    """Create a backend; defaults keep both DB writes and email delivery off.

    No calls to database or network are made during construction.
    Returning a backend is NOT permission to expose it through any router.
    """
    if not isinstance(material,PrivateConsumerCredentialMaterial):
        raise ValueError("PRIVATE_MATERIAL_REQUIRED")
    keys=Keys(
        email_hmac=material.email_hmac,
        token_hmac=material.token_hmac,
        email_encryption=material.email_encryption,
        email_key_reference=material.key_reference,
    )
    keys.validate()
    # Pass an isolated, validated local login; never reuse global EmpireDB.
    dsn=make_conninfo(
        host="127.0.0.1",port=5432,dbname="empiredb",
        user=LOGIN,password=material.db_password,
    )
    factory=PrivateConsumerConnectionFactory(
        dsn=dsn,
        owner_authorized=owner_approved_private_custody is True,
        connect=db_connect,
    )
    store=LiveReadbackConsumerRepository(
        connection_factory=factory,
        approved_custody=owner_approved_private_custody is True,
    )
    suppression=ConsumerPrivateSuppressionReader(
        connect=factory,lookup_key=keys.email_hmac,
        approved_private_custody=owner_approved_private_custody is True,
    )
    kwargs={}
    if resend_provider is not None:
        if not callable(resend_provider):
            raise ValueError("AUTHORISED_SENDER_PROVIDER_REQUIRED")
        kwargs["provider"]=resend_provider
    sender=ResendConsumerConfirmationSender(
        api_key=resend_scoped_key or "DISABLED_NO_SEND_KEY",
        verified_sender_domain=sender_domain_independently_verified is True,
        owner_approved_consumer_confirmation=owner_approved_confirmation_send is True,
        current_suppression_clear=suppression,
        **kwargs,
    )
    return PrivateConsumerOptinService(keys=keys,store=store,sender=sender)
