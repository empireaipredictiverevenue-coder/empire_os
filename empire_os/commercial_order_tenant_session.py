"""Canonical exact-order operator: authenticated tenant session capability gate.

The CLI must never use the broad application DSN. This guard runs BEFORE
any canonical order/payment SELECT, on the same PostgreSQL transaction used
by the original owner reader. The tenant is taken from an authenticated
session_user->tenant binding, not a user-supplied UUID or SET ROLE alone.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

REQUIRED_RELATIONS = (
    "public.buyers",
    "public.fulfilment_orders",
    "public.commercial_outcomes",
    "public.commercial_events",
    "public.bsc_payment_requests",
    "public.bsc_payment_evidence",
    "public.bsc_escrow_agreements",
    "public.bsc_escrow_evidence",
)
READER_ROLE = "empiredb_tenant_reader"
READ_ONLY_SQL = """
SELECT session_user::text, current_user::text,
       pg_catalog.pg_has_role(session_user,'empiredb_tenant_reader','MEMBER'),
       r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
       current_database()::text,current_setting('transaction_read_only')::text
FROM pg_catalog.pg_roles AS r WHERE r.rolname=session_user
"""
READER_PROOF_SQL = """
SELECT session_user::text,current_user::text,
       public.empire_current_tenant_id()::text,
       current_setting('transaction_read_only')::text,
       pg_catalog.has_table_privilege(current_user,%s::text,'SELECT'),
       pg_catalog.row_security_active(%s::regclass)
"""
MAX_TENANT_LENGTH = 40


class TenantOrderSessionHeld(ValueError):
    """Safe output status only; no SQL credentials or tenant IDs in message."""


def _tenant_uuid(value: Any) -> str:
    if not isinstance(value, str) or len(value) > MAX_TENANT_LENGTH:
        raise TenantOrderSessionHeld("UNAUTHORIZED_TENANT_SCOPE")
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise TenantOrderSessionHeld("UNAUTHORIZED_TENANT_SCOPE") from exc
    if str(parsed) != value.lower() or parsed.version not in (4, 7):
        raise TenantOrderSessionHeld("UNAUTHORIZED_TENANT_SCOPE")
    return str(parsed)


def _row(executor, sql: str, params: tuple = ()):
    """Read bounded metadata; PG SQL_ASCII installations can return text as bytes."""
    raw = executor.execute(sql, params).fetchone()
    if not isinstance(raw, (tuple, list)):
        raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE")
    fields = []
    for value in raw:
        if isinstance(value, bytes):
            if len(value) > 128:
                raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE")
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE") from exc
        fields.append(value)
    return tuple(fields)


def prove_exact_tenant_readonly_session(snapshot: Any, *, tenant_id: str) -> dict:
    """Prove role-to-tenant identity, nonprivileged read-only context and RLS.

    This function deliberately has a narrow internal use: the original
    _EmpireDbReadOnlySnapshot obtained from the existing provider.
    """
    tenant = _tenant_uuid(tenant_id)
    session = getattr(snapshot, "_session", None)
    if session is None or getattr(snapshot, "state", None) != "active":
        raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE")
    try:
        initial = _row(session, READ_ONLY_SQL)
    except TenantOrderSessionHeld:
        raise
    except Exception as exc:
        raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE") from exc
    if len(initial) != 10:
        raise TenantOrderSessionHeld("TENANT_SESSION_PROOF_UNAVAILABLE")
    (
        login, current_role, member,
        superuser, bypass, createdb, createrole, replication,
        database, read_only,
    ) = initial
    if (
        not isinstance(login, str)
        or login in {"postgres", "empiredb_app", "empiredb_readonly", "empiredb_migrator", READER_ROLE}
        or current_role != login
        or member is not True
        or any(value is not False for value in
               (superuser, bypass, createdb, createrole, replication))
        or database != "empiredb"
        or read_only != "on"
    ):
        raise TenantOrderSessionHeld("TENANT_SESSION_IDENTITY_OR_ROLE_HOLD")
    try:
        # Fixed literal role, no user-provided SQL identifier.
        session.execute("SET LOCAL ROLE empiredb_tenant_reader")
        for relation in REQUIRED_RELATIONS:
            (
                unchanged_login, active_role, bound, still_readonly,
                select_granted, rls_active,
            ) = _row(session, READER_PROOF_SQL, (relation, relation))
            if (
                unchanged_login != login
                or active_role != READER_ROLE
                or bound != tenant
                or still_readonly != "on"
                or select_granted is not True
                or rls_active is not True
            ):
                raise TenantOrderSessionHeld("TENANT_READER_ACL_OR_RLS_HOLD")
    except TenantOrderSessionHeld:
        raise
    except Exception as exc:
        raise TenantOrderSessionHeld("TENANT_READER_ACL_OR_RLS_HOLD") from exc
    return {
        "schema_version": "empire.commercial.verified_order_tenant_session.v1",
        "status": "TENANT_SCOPED_READONLY_RLS_SESSION_VERIFIED",
        "verified_relation_count": len(REQUIRED_RELATIONS),
        "tenant_identity_resolved_from_original_db_session": True,
        "caller_tenant_matches_session_binding": True,
        "database_read_only_transaction": True,
        "nonprivileged_tenant_login": True,
        "no_order_or_payment_rows_queried": True,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
