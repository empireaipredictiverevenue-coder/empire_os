"""Audit ORIGINAL forecast-registry rows with EXISTING EmpireDB tenant read access.

This does not create a grant, role, reader secret, registration, forecast or
commercial result. A scoped forecast row is only a CANDIDATE original receipt,
not cryptographically frozen, pre-outcome or independently attested evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_tenant_outcome_reader_preflight import (
    IDENTITY_SQL, ROLE_SQL, READER_ROLE, _role,
)

SCHEMA = "empire.predictive_revenue.existing_tenant_registry_receipts.v1"
MAX_ROWS = 100
METRIC = "recognized_revenue_cents"
REGISTRY_META_SQL = """
SELECT c.relrowsecurity, c.relforcerowsecurity,
       has_table_privilege(current_user,c.oid,'SELECT'),
       has_table_privilege(current_user,c.oid,'UPDATE'),
       has_table_privilege(current_user,c.oid,'DELETE')
FROM pg_catalog.pg_class c
WHERE c.oid=pg_catalog.to_regclass('public.predictive_forecasts')
""".strip()
REGISTRY_POLICY_SQL = """
SELECT policyname::text,cmd::text,roles::text[],qual::text
FROM pg_catalog.pg_policies
WHERE schemaname='public' AND tablename='predictive_forecasts'
ORDER BY policyname
""".strip()
ROWS_SQL = """
SELECT f.id::text,f.forecast_key,f.dimension_key,f.metric,
       f.predicted_value,f.generated_at
FROM public.predictive_forecasts f
WHERE f.dimension_key=('tenant:' || public.empire_current_tenant_id()::text)
  AND f.metric=%s
ORDER BY f.generated_at DESC,f.id DESC
LIMIT %s
""".strip()


class RegistrySourceHeld(ValueError):
    """Sanitized refusal; do not leak SQL error, tenant, source row or DSN."""


def _id(item: Any) -> bool:
    if type(item) is not str:
        return False
    try:
        return str(UUID(item)) == item
    except (TypeError, ValueError):
        return False


def _clock(item: Any, now: datetime) -> bool:
    return (isinstance(item, datetime) and item.utcoffset() is not None
            and item.astimezone(timezone.utc) <= now)


def _admitted_metadata(meta: Any, policies: Any) -> bool:
    if (type(meta) not in (tuple, list) or len(meta) != 5
            or any(type(x) is not bool for x in meta)
            or tuple(meta) != (True, True, True, False, False)):
        return False
    if type(policies) is not list or len(policies) != 1:
        # A second permissive policy can broaden tenant visibility.
        return False
    record = policies[0]
    if type(record) not in (tuple, list) or len(record) != 4:
        return False
    policy, command, roles, expression = record
    if (type(policy) is not str or not policy
            or command != "SELECT" or roles != [READER_ROLE]
            or type(expression) is not str):
        return False
    # This is only an admission guard, not a SQL theorem prover.
    # Any changed SQL shape requires a human-reviewed custody update.
    normalized = "".join(expression.lower().split())
    if (not all(token in normalized for token in (
            "dimension_key", "tenant:", "empire_current_tenant_id()"))
            or " or " in expression.lower() or "ortrue" in normalized
            or "1=1" in normalized):
        return False
    return True


def _candidates(rows: Any, *, tenant: str, now: datetime) -> dict[str, Any]:
    if type(rows) is not list or len(rows) > MAX_ROWS + 1:
        raise RegistrySourceHeld("source bound not demonstrated")
    if len(rows) > MAX_ROWS:
        return {
            "status": "TENANT_REGISTRY_READ_BOUND_HOLD",
            "registry_candidate_count": MAX_ROWS,
            "registry_read_complete": False,
            "earliest_registry_candidate_at_utc": None,
            "latest_registry_candidate_at_utc": None,
        }
    keys: set[str] = set()
    ids: set[str] = set()
    registered: list[datetime] = []
    for row in rows:
        if type(row) not in (tuple, list) or len(row) != 6:
            raise RegistrySourceHeld("registry row shape invalid")
        identity, key, scope, metric, amount, when = row
        if (not _id(identity) or identity in ids
                or type(key) is not str or not 1 <= len(key) <= 180
                or key in keys or scope != "tenant:" + tenant
                or metric != METRIC or not _clock(when, now)
                or type(amount) not in (int, Decimal)
                or isinstance(amount, bool)
                or not 0 <= amount <= 9_000_000_000_000_000
                or int(amount) != amount):
            raise RegistrySourceHeld("registry evidence or tenant invalid")
        keys.add(key)
        ids.add(identity)
        registered.append(when.astimezone(timezone.utc))
    return {
        "status": (
            "AUTHENTICATED_TENANT_REGISTRY_CANDIDATES_ORIGIN_UNVERIFIED"
            if rows else "AUTHENTICATED_TENANT_REGISTRY_EMPTY"
        ),
        "registry_candidate_count": len(rows),
        "registry_read_complete": False,  # bounded as-of, never lifetime
        "earliest_registry_candidate_at_utc": (
            min(registered).isoformat() if registered else None
        ),
        "latest_registry_candidate_at_utc": (
            max(registered).isoformat() if registered else None
        ),
    }


def read_existing_tenant_registry_receipts(
    *, dsn: str, now: datetime | None = None,
    connect_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if type(dsn) is not str or not dsn.strip():
        raise RegistrySourceHeld("existing read-only credential missing")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise RegistrySourceHeld("trusted review time missing")
    now = now.astimezone(timezone.utc)
    if connect_factory is None:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError:
            raise RegistrySourceHeld("driver unavailable") from None
    try:
        with connect_factory(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                cursor.execute(IDENTITY_SQL)
                identity = cursor.fetchone()
                if (type(identity) not in (tuple, list) or len(identity) != 5):
                    raise RegistrySourceHeld("session identity unavailable")
                database, readonly, login_role, role, tenant = identity
                if (database != "empiredb" or readonly != "on"
                        or type(login_role) is not str
                        or login_role in ("", "postgres", READER_ROLE)
                        or role != READER_ROLE or not _id(tenant)):
                    raise RegistrySourceHeld("original tenant session unavailable")
                cursor.execute(ROLE_SQL, (login_role,))
                login = cursor.fetchone()
                cursor.execute(ROLE_SQL, (READER_ROLE,))
                reader = cursor.fetchone()
                if not (_role(login, login=True)
                        and _role(reader, login=False)):
                    raise RegistrySourceHeld("reader role unsafe")
                cursor.execute(REGISTRY_META_SQL)
                metadata = cursor.fetchone()
                cursor.execute(REGISTRY_POLICY_SQL)
                policies = cursor.fetchall()
                if not _admitted_metadata(metadata, policies):
                    # Crucially, NO registry SELECT is attempted with
                    # mismatched grants/RLS/policy or missing table.
                    result = {
                        "status": "EXISTING_READER_REGISTRY_NOT_ADMITTED",
                        "registry_candidate_count": None,
                        "registry_read_complete": False,
                        "earliest_registry_candidate_at_utc": None,
                        "latest_registry_candidate_at_utc": None,
                    }
                else:
                    cursor.execute(ROWS_SQL, (METRIC, MAX_ROWS + 1))
                    result = _candidates(
                        cursor.fetchall(), tenant=tenant, now=now
                    )
    except Exception:
        raise RegistrySourceHeld("original registry read unavailable") from None
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        **result,
        "canonical_database": "EmpireDB",
        "existing_tenant_reader_session_authenticated": True,
        "existing_reader_registry_source_admitted": (
            result["status"] not in ("EXISTING_READER_REGISTRY_NOT_ADMITTED",)
        ),
        "registry_role_or_permissions_created": False,
        "original_forecast_immutable_registration_verified": False,
        "forecast_registered_before_outcome_verified": False,
        "independent_revenue_settlement_verified": False,
        "original_registry_ids_or_customer_values_exposed": False,
        "customer_training_labels_admitted": False,
        "customer_forecast_eligible": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_action": False,
        "execution_authority": "none",
    }
