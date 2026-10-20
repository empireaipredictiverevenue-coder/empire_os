"""Read-only EmpireDB tenant-outcome reader policy inventory.

Inspects only pg_catalog and the DB-derived session tenant. Never SELECTs
private commercial rows and never provisions credentials, roles or RLS.
A passing inventory is NOT original outcome provenance or release authority.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

SCHEMA = "empire.predictive_revenue.tenant_outcome_reader_policy_preflight.v1"
READER_ROLE = "empiredb_tenant_reader"
TABLE_POLICY = {
    "buyers": "buyers_tenant_reader_select",
    "fulfilment_orders": "fulfilment_orders_tenant_reader_select",
    "commercial_events": "commercial_events_tenant_reader_select",
    "commercial_outcomes": "commercial_outcomes_tenant_reader_select",
}
ROLE_SQL = (
    "SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit "
    "FROM pg_catalog.pg_roles WHERE rolname=%s"
)
IDENTITY_SQL = (
    "SELECT current_database(),current_setting('transaction_read_only'),"
    "session_user::text,current_user::text,"
    "public.empire_current_tenant_id()::text"
)
TABLE_SQL = """
SELECT c.relname::text,c.relrowsecurity,c.relforcerowsecurity,
       has_table_privilege(current_user,c.oid,'SELECT')
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
  AND c.relname=ANY(%s::text[])
ORDER BY c.relname
""".strip()
POLICY_SQL = """
SELECT tablename::text,policyname::text,cmd::text,
       roles::text[],qual::text
FROM pg_catalog.pg_policies
WHERE schemaname='public' AND tablename=ANY(%s::text[])
ORDER BY tablename,policyname
""".strip()


class TenantEvidencePolicyHold(ValueError):
    """Source role or metadata untrusted; details intentionally redacted."""


def _role(row: Any, *, login: bool) -> bool:
    if type(row) not in (tuple, list) or len(row) != 4:
        return False
    if any(type(x) is not bool for x in row):
        return False
    can_login, superuser, bypass_rls, inherits = row
    return can_login is login and not (superuser or bypass_rls or inherits)


def _catalogue(
    rows: Any, policies: Any,
) -> dict[str, Any]:
    if type(rows) is not list or len(rows) > 50 or type(policies) is not list or len(policies) > 100:
        raise TenantEvidencePolicyHold("unexpected policy metadata volume")
    inventory: dict[str, dict[str, bool]] = {}
    for item in rows:
        if type(item) not in (tuple, list) or len(item) != 4:
            raise TenantEvidencePolicyHold("table metadata invalid")
        name, enabled, forced, selectable = item
        if (type(name) is not str or name not in TABLE_POLICY
                or name in inventory or any(type(x) is not bool for x in
                (enabled, forced, selectable))):
            raise TenantEvidencePolicyHold("table metadata invalid")
        inventory[name] = {
            "rls_enabled": enabled,
            "rls_forced": forced,
            "reader_select_granted": selectable,
            "expected_scoped_policy_found": False,
        }
    seen = set()
    for item in policies:
        if type(item) not in (tuple, list) or len(item) != 5:
            raise TenantEvidencePolicyHold("policy record invalid")
        name, policy, cmd, roles, expression = item
        if (type(name) is not str or name not in TABLE_POLICY
                or type(policy) is not str or type(cmd) is not str
                or type(roles) is not list
                or any(type(r) is not str for r in roles)
                or type(expression) not in (str, type(None))):
            raise TenantEvidencePolicyHold("policy record invalid")
        if (name, policy) in seen:
            raise TenantEvidencePolicyHold("duplicate policy metadata")
        seen.add((name, policy))
        if policy == TABLE_POLICY[name]:
            scoped = (
                cmd == "SELECT"
                and roles == [READER_ROLE]
                and expression is not None
                and "empire_current_tenant_id" in expression
                and not any(bad in expression.lower() for bad in
                            (" or true", " = true", "1 = 1"))
            )
            if name in inventory:
                inventory[name]["expected_scoped_policy_found"] = scoped
    result = {}
    for name in TABLE_POLICY:
        flags = inventory.get(name) or {
            "rls_enabled": False,
            "rls_forced": False,
            "reader_select_granted": False,
            "expected_scoped_policy_found": False,
        }
        result[name] = flags
    return result


def review_tenant_outcome_reader_policy(
    *, dsn: str, connect_factory: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """No row query. Authenticated DB-session identity is server-derived.

    Metadata checks gate database-owner review only; RLS policy text is not
    accepted as complete proof of isolation or historical outcomes.
    """
    if type(dsn) is not str or not dsn.strip():
        raise TenantEvidencePolicyHold("dedicated tenant reader DSN required")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError:
            raise TenantEvidencePolicyHold("database driver unavailable") from None
        connect_factory = psycopg.connect
    if not callable(connect_factory):
        raise TenantEvidencePolicyHold("reader transport invalid")
    try:
        with connect_factory(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                cursor.execute(IDENTITY_SQL)
                identity = cursor.fetchone()
                if (type(identity) not in (list, tuple) or len(identity) != 5):
                    raise TenantEvidencePolicyHold("session identity unavailable")
                database, readonly, login_role, current_role, tenant = identity
                if (database != "empiredb" or readonly != "on"
                        or type(login_role) is not str or not login_role
                        or login_role in ("postgres", READER_ROLE)
                        or current_role != READER_ROLE
                        or type(tenant) is not str or not tenant):
                    raise TenantEvidencePolicyHold("trusted session tenant not proven")
                from uuid import UUID
                if str(UUID(tenant)) != tenant.lower():
                    raise TenantEvidencePolicyHold("canonical session tenant missing")
                cursor.execute(ROLE_SQL, (login_role,))
                login = cursor.fetchone()
                cursor.execute(ROLE_SQL, (READER_ROLE,))
                role = cursor.fetchone()
                if not (_role(login, login=True) and _role(role, login=False)):
                    raise TenantEvidencePolicyHold("unsafe login or read role")
                cursor.execute(TABLE_SQL, (list(TABLE_POLICY),))
                tables = cursor.fetchall()
                cursor.execute(POLICY_SQL, (list(TABLE_POLICY),))
                policies = cursor.fetchall()
        table_report = _catalogue(tables, policies)
    except Exception:
        raise TenantEvidencePolicyHold("tenant database metadata reader unavailable") from None
    issues = sorted(
        f"{table}.{key}"
        for table, flags in table_report.items()
        for key, ok in flags.items() if not ok
    )
    return {
        "schema_version": SCHEMA,
        "status": ("TENANT_SOURCE_POLICY_METADATA_REVIEW_READY"
                   if not issues else "TENANT_SOURCE_POLICY_GAPS_OBSERVED"),
        "mode": "OBSERVE",
        "database_name_verified": True,
        "transaction_read_only_verified": True,
        "session_tenant_resolved_by_db_role": True,
        "tenant_id_or_customer_rows_exported": False,
        "login_role_least_privilege_shape_verified": True,
        "tenant_reader_nologin_noinherit_nobypassrls_verified": True,
        "table_policy_inventory": table_report,
        "policy_gap_codes": issues,
        "source_issuer_verified": False,
        "authenticated_terminal_outcomes_read": False,
        "original_conversion_prediction_registry_verified": False,
        "commercial_outcomes_provenance_verified": False,
        "tenant_safe_data_reader_activated": False,
        "customer_forecast_eligible": False,
        "database_writes": False,
        "role_or_rls_changed": False,
        "execution_authority": "none",
    }
