"""One-shot, aggregate-only production CRM login preflight.

No customer rows, tenant IDs, role names, database credentials, or
connection strings are printed. No database role grants or writes.
Requires an authorised operator for local PostgreSQL catalog access.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def classify(app_database: str, app_epoch: int, catalog: dict[str, Any]) -> dict[str, Any]:
    same_instance = (
        app_database == "empiredb"
        and catalog.get("database") == "empiredb"
        and app_epoch == catalog.get("postmaster_epoch")
    )
    login_found = catalog.get("app_login_present") is True
    safe = (
        login_found
        and catalog.get("app_login_elevated") is False
        and catalog.get("app_login_binding_update") is False
    )
    return {
        "schema": "empire.revenue-crm.application-login-preflight.v1",
        "mode": "OBSERVE",
        "catalog_read_only": True,
        "customer_rows_read": False,
        "credentials_logged": False,
        "canonical_database_instance_verified": same_instance,
        "app_login_present": login_found,
        "app_login_low_privilege": safe,
        "app_login_has_active_tenant_binding": catalog.get("app_login_bound") is True,
        "app_login_binding_evidence_present": catalog.get("app_login_evidenced") is True,
        "app_login_crm_role_member": catalog.get("app_login_crm_member") is True,
        "app_login_crm_view_select": catalog.get("app_login_crm_select") is True,
        "app_login_crm_buyer_view_select": catalog.get("app_login_crm_buyer_select") is True,
        "crm_two_views_present": catalog.get("crm_two_views_present") is True,
        "crm_views_security_invoker": catalog.get("crm_views_security_invoker") is True,
        "crm_views_security_barrier": catalog.get("crm_views_security_barrier") is True,
        "crm_source_tables_rls_enabled": catalog.get("crm_source_tables_rls_enabled") is True,
        "app_can_select_base_source_columns": catalog.get("app_base_columns_select") is True,
        "crm_view_select_grant_public": catalog.get("crm_grant_public") is True,
        "crm_view_select_grant_direct_app": catalog.get("crm_grant_direct_app") is True,
        "crm_view_select_grant_inherited": catalog.get("crm_grant_inherited") is True,
        "crm_view_owned_by_app": catalog.get("crm_view_owned_by_app") is True,
        "crm_view_effective_permission_without_reader_membership": (
            catalog.get("app_login_crm_select") is True
            and catalog.get("app_login_crm_member") is False
        ),
        "app_login_can_mutate_tenant_binding": catalog.get("app_login_binding_update") is True,
        "independent_active_bound_logins": int(catalog.get("other_bound_logins", 0)),
        "independent_evidenced_bound_logins": int(catalog.get("other_evidenced_logins", 0)),
        "live_cross_tenant_proof": False,
        "http_tenant_authentication_verified": False,
        "app_activation_authorized": False,
        "role_changes_performed": False,
    }


def build_catalog_statement(quoted_login: str) -> str:
    """Return catalog-only SQL for a safely quoted app role name."""
    return f"""
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5000ms';
WITH target AS (
 SELECT r.oid, r.rolname, r.rolcanlogin, r.rolsuper, r.rolcreatedb,
        r.rolcreaterole, r.rolbypassrls, r.rolreplication
 FROM pg_catalog.pg_roles r WHERE r.rolname = {quoted_login}
), login_status AS (
 SELECT
  count(*)=1 AS app_login_present,
  coalesce(bool_or(rolsuper OR rolcreatedb OR rolcreaterole
                   OR rolbypassrls OR rolreplication),false) AS app_login_elevated,
  coalesce(bool_or(pg_catalog.pg_has_role(
       oid,'empire_revenue_crm_reader'::regrole,'MEMBER')),false)
       AS app_login_crm_member,
  coalesce(bool_or(pg_catalog.has_table_privilege(
       oid,'public.revenue_crm_prospects','SELECT')),false)
       AS app_login_crm_select,
  coalesce(bool_or(pg_catalog.has_table_privilege(
       oid,'public.revenue_crm_buyers','SELECT')),false)
       AS app_login_crm_buyer_select,
  coalesce(bool_or(pg_catalog.has_table_privilege(
       oid,'public.empire_tenant_role_bindings','UPDATE')),false)
       AS app_login_binding_update
 FROM target
), bindings AS (
 SELECT count(*) FILTER (WHERE b.role_name = {quoted_login}) > 0
         AS app_login_bound,
        count(*) FILTER (
          WHERE b.role_name = {quoted_login}
            AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        ) > 0 AS app_login_evidenced,
        count(*) FILTER (
          WHERE b.role_name <> {quoted_login}
            AND r.rolcanlogin AND NOT r.rolsuper
        ) AS other_bound_logins,
        count(*) FILTER (
          WHERE b.role_name <> {quoted_login}
            AND r.rolcanlogin AND NOT r.rolsuper
            AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        ) AS other_evidenced_logins
 FROM public.empire_tenant_role_bindings b
 JOIN pg_catalog.pg_roles r ON b.role_name=r.rolname
 WHERE b.active
), crm_acl AS (
 SELECT
    count(DISTINCT v.oid) = 2 AS crm_two_views_present,
    coalesce(bool_and(coalesce('security_invoker=true'=ANY(v.reloptions),false)),false)
        AS crm_views_security_invoker,
    coalesce(bool_and(coalesce('security_barrier=true'=ANY(v.reloptions),false)),false)
        AS crm_views_security_barrier,
    coalesce(bool_or(
       a.privilege_type='SELECT' AND a.grantee=0
    ),false) AS crm_grant_public,
    coalesce(bool_or(
       a.privilege_type='SELECT' AND a.grantee=t.oid
    ),false) AS crm_grant_direct_app,
    coalesce(bool_or(CASE WHEN
       a.privilege_type='SELECT' AND a.grantee<>0
       AND a.grantee<>t.oid
       THEN pg_catalog.pg_has_role(t.oid,a.grantee,'USAGE')
       ELSE false END),false) AS crm_grant_inherited,
    coalesce(bool_or(v.relowner=t.oid),false) AS crm_view_owned_by_app
 FROM pg_catalog.pg_class v
 JOIN pg_catalog.pg_namespace n ON v.relnamespace=n.oid
 CROSS JOIN target t
 LEFT JOIN LATERAL pg_catalog.aclexplode(
     coalesce(v.relacl,pg_catalog.acldefault('v',v.relowner))
 ) a ON true
 WHERE n.nspname='public'
   AND v.relname IN ('revenue_crm_prospects','revenue_crm_buyers')
   AND v.relkind='v'
), crm_base AS (
 SELECT
   count(DISTINCT c.oid) = 2
      AND coalesce(bool_and(c.relrowsecurity),false)
      AS crm_source_tables_rls_enabled,
   coalesce(bool_or(
      pg_catalog.has_any_column_privilege(t.oid,c.oid,'SELECT')
   ),false) AS app_base_columns_select
 FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON c.relnamespace=n.oid
 CROSS JOIN target t
 WHERE n.nspname='public' AND c.relname IN ('prospects','buyers')
)
SELECT row_to_json(result)
FROM (
 SELECT current_database() AS database,
        extract(epoch from pg_postmaster_start_time())::bigint
          AS postmaster_epoch,
        login_status.*, bindings.*, crm_acl.*, crm_base.*
 FROM login_status CROSS JOIN bindings
 CROSS JOIN crm_acl CROSS JOIN crm_base
) result;
COMMIT;
"""

def main() -> int:
    blocked = {
        "schema": "empire.revenue-crm.application-login-preflight.v1",
        "mode": "OBSERVE",
        "status": "BLOCKED",
        "app_activation_authorized": False,
        "role_changes_performed": False,
        "customer_rows_read": False,
    }
    try:
        if os.geteuid() != 0:
            raise ValueError("AUTHORIZED_ROOT_REQUIRED")
        dsn = os.environ.get("EMPIREDB_DSN", "").strip()
        if not dsn:
            raise ValueError("APP_DATABASE_DSN_NOT_CONFIGURED")
        import psycopg
        from psycopg import sql
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as c:
                c.execute("SET TRANSACTION READ ONLY")
                c.execute("SET LOCAL statement_timeout = '5000ms'")
                c.execute(
                    "SELECT current_database(), session_user,"
                    " extract(epoch from pg_postmaster_start_time())::bigint"
                )
                db, login, epoch = c.fetchone()
            safe_login = sql.Literal(str(login)).as_string(conn)
        statement = build_catalog_statement(safe_login)
        process = subprocess.run(
            ["runuser", "-u", "postgres", "--", "psql", "-X", "-w",
             "-q", "-At", "-v", "ON_ERROR_STOP=1", "-d", "empiredb",
             "-c", statement],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if process.returncode != 0:
            raise ValueError("LOCAL_CATALOG_ACCESS_FAILED")
        records = [line for line in process.stdout.splitlines()
                   if line.strip().startswith("{")]
        if len(records) != 1:
            raise ValueError("CATALOG_FORMAT_INVALID")
        catalog = json.loads(records[0])
        result = classify(str(db), int(epoch), catalog)
        result["status"] = (
            "READ_ONLY_INVENTORY_VERIFIED"
            if result["canonical_database_instance_verified"]
            else "BLOCKED_DIFFERENT_DATABASE_INSTANCE"
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "READ_ONLY_INVENTORY_VERIFIED" else 2
    except Exception:
        # Error content can contain passwords/DSNs; never print exceptions.
        blocked["reason"] = "APP_LOGIN_PREFLIGHT_UNAVAILABLE"
        print(json.dumps(blocked, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
