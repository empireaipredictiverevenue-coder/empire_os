"""Existing-role, tenant-locked EmpireDB adapter for JEV founder research.

This adapter provisions NOTHING. It requires a separately configured
dedicated NOINHERIT login with only the existing empiredb_tenant_reader
role. Session-user tenant binding comes from the server-side resolver.
Never accepts a tenant ID from request parameters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from empire_os.jev_gtm_founder_review import build_jev_founder_economic_review

ROLE = "empiredb_tenant_reader"
AUTHORITY_SQL = (
    "SELECT "
    "pg_catalog.pg_has_role(session_user,"
    "'empiredb_tenant_reader'::pg_catalog.regrole,'MEMBER'),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE "
    "r.rolname <> 'empiredb_tenant_reader' "
    "AND r.rolname <> session_user "
    "AND pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=session_user "
    "AND (NOT r.rolcanlogin OR r.rolinherit OR r.rolsuper OR "
    "r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR r.rolreplication)),"
    "pg_catalog.pg_has_role(session_user,"
    "'empiredb_tenant_reader'::pg_catalog.regrole,'USAGE')"
)


class JevEconomicResearchReadUnavailable(RuntimeError):
    """Sanitised reader denial: never return credentials or source details."""


class PostgresJevEconomicResearchReader:
    """Dedicated login, exact authenticated tenant, one bounded entity read."""

    def __init__(
        self, dsn: str, *, authenticated_tenant_id: str,
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        try:
            tenant = str(UUID(str(authenticated_tenant_id)))
        except (TypeError, ValueError, AttributeError):
            raise JevEconomicResearchReadUnavailable("trusted tenant identity required") from None
        if not isinstance(dsn, str) or not dsn.strip():
            raise JevEconomicResearchReadUnavailable("dedicated economic reader DSN required")
        if connect_factory is None:
            try:
                import psycopg
            except ImportError:
                raise JevEconomicResearchReadUnavailable("PostgreSQL driver unavailable") from None
            connect_factory = psycopg.connect
        self._tenant = tenant
        self._dsn = dsn.strip()
        self._connect = connect_factory

    def read(self, *, entity_id: str, as_of: datetime | None = None) -> dict[str, Any]:
        try:
            entity = str(UUID(str(entity_id)))
        except (ValueError, TypeError, AttributeError):
            raise JevEconomicResearchReadUnavailable("canonical entity UUID required") from None
        instant = as_of if as_of is not None else datetime.now(timezone.utc)
        if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
            raise JevEconomicResearchReadUnavailable("timezone-aware instant required")
        try:
            with self._connect(self._dsn, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                    cursor.execute("SET LOCAL lock_timeout = '2000ms'")
                    cursor.execute(AUTHORITY_SQL)
                    role = cursor.fetchone()
                    if not isinstance(role, (tuple, list)) or tuple(role) != (
                        True, False, False, False,
                    ):
                        raise JevEconomicResearchReadUnavailable("dedicated reader authority invalid")
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute("SELECT public.empire_current_tenant_id()")
                    row = cursor.fetchone()
                    if not isinstance(row, (tuple, list)) or len(row) != 1 or str(row[0]) != self._tenant:
                        raise JevEconomicResearchReadUnavailable("authenticated tenant mismatch")
                    result = build_jev_founder_economic_review(
                        cursor, entity_id=entity, as_of=instant,
                    )
                    if (result.get("execution_authority") != "none"
                            or result.get("contains_contact_data") is not False
                            or result.get("outbound_sent") is not False
                            or result.get("source_authorised_commercial_action") is not False):
                        raise JevEconomicResearchReadUnavailable("unsafe founder result")
                    return result
        except JevEconomicResearchReadUnavailable:
            raise
        except Exception:
            raise JevEconomicResearchReadUnavailable(
                "canonical economic research source unavailable"
            ) from None
