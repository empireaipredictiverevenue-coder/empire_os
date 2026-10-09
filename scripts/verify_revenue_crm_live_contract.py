"""Read-only catalog preflight for the existing Revenue CRM transport.

Never reads customer rows, tenant identifiers, credentials, or mail.
Catalog readiness is a prerequisite only: production login isolation and
authenticated source/tenant binding require a separate acceptance proof.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from empire_os.revenue_crm_transport import (
    BUYER_COLUMNS, PROSPECT_COLUMNS, ROLE,
)
from empire_os.revenue_crm_source_schema import inspect_source_schema

VIEWS = {
    "prospects": ("public.revenue_crm_prospects", PROSPECT_COLUMNS.split(",")),
    "buyers": ("public.revenue_crm_buyers", BUYER_COLUMNS.split(",")),
}

def _block(issues: list[str], ok: bool, code: str) -> None:
    if not ok:
        issues.append(code)


def _columns(cursor: Any, oid: int) -> set[str]:
    cursor.execute(
        "SELECT attname FROM pg_catalog.pg_attribute "
        "WHERE attrelid=%s AND attnum>0 AND NOT attisdropped",
        (oid,),
    )
    return {str(row[0]) for row in cursor.fetchall()}


def _base_dependencies(cursor: Any, oid: int) -> list[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT DISTINCT related.oid, related.relkind,
                        related.relrowsecurity, related.reloptions
          FROM pg_catalog.pg_rewrite rule
          JOIN pg_catalog.pg_depend dep
            ON dep.classid='pg_catalog.pg_rewrite'::pg_catalog.regclass
           AND dep.objid=rule.oid
           AND dep.refclassid='pg_catalog.pg_class'::pg_catalog.regclass
          JOIN pg_catalog.pg_class related ON related.oid=dep.refobjid
          JOIN pg_catalog.pg_namespace ns ON ns.oid=related.relnamespace
         WHERE rule.ev_class=%s AND related.oid<>rule.ev_class
           AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
        """,
        (oid,),
    )
    return list(cursor.fetchall())


def inspect_crm_catalog(cursor: Any) -> dict[str, Any]:
    """Return only allowlisted status booleans/reasons, not catalog data."""
    issues: list[str] = []
    cursor.execute(
        "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname=%s", (ROLE,),
    )
    role = cursor.fetchone()
    role_safe = (
        isinstance(role, (tuple, list)) and len(role) == 3
        and role[0] is False and role[1] is False and role[2] is False
    )
    _block(issues, role_safe, "CRM_READER_ROLE_MISSING_OR_UNSAFE")

    cursor.execute(
        "SELECT p.prosecdef FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proname='empire_current_tenant_id' "
        "AND p.pronargs=0"
    )
    function = cursor.fetchone()
    _block(
        issues, function is not None and function[0] is True,
        "TRUSTED_TENANT_FUNCTION_NOT_VERIFIED",
    )
    cursor.execute(
        "SELECT p.prosecdef,p.provolatile,owner.rolname "
        "FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
        "JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner "
        "WHERE n.nspname='public' AND p.proname='empire_crm_prospect_authorized' "
        "AND pg_catalog.pg_get_function_identity_arguments(p.oid)='p_prospect_id uuid'"
    )
    helper = cursor.fetchone()
    helper_safe = (
        isinstance(helper,(tuple,list))
        and len(helper)==3 and helper==(True,"s","empiredb_migrator")
    )
    details = {}
    for label, (name, cols) in VIEWS.items():
        cursor.execute(
            "SELECT c.oid, c.relkind, c.reloptions "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=%s",
            (name.split(".")[1],),
        )
        found = cursor.fetchone()
        if not found or found[1] != "v":
            _block(issues, False, f"{label.upper()}_VIEW_MISSING_OR_NOT_VIEW")
            details[label] = {
                "present": False, "columns_complete": False,
                "security_invoker": False, "base_rls_verified": False,
                "role_select_only": False,
            }
            continue
        oid, _, opts = found
        options = {str(v).lower() for v in (opts or [])}
        invoker = "security_invoker=true" in options
        complete = set(cols).issubset(_columns(cursor, oid))
        _block(issues, invoker, f"{label.upper()}_VIEW_NOT_SECURITY_INVOKER")
        _block(issues, complete, f"{label.upper()}_VIEW_COLUMNS_MISSING")

        select_only = False
        if role_safe:
            cursor.execute(
                "SELECT pg_catalog.has_table_privilege(%s,%s,'SELECT'),"
                "pg_catalog.has_table_privilege(%s,%s,'INSERT'),"
                "pg_catalog.has_table_privilege(%s,%s,'UPDATE'),"
                "pg_catalog.has_table_privilege(%s,%s,'DELETE')",
                (ROLE, oid, ROLE, oid, ROLE, oid, ROLE, oid),
            )
            grants = cursor.fetchone()
            select_only = grants == (True, False, False, False)
        _block(issues, select_only, f"{label.upper()}_ROLE_READ_GRANTS_NOT_SAFE")

        bases = _base_dependencies(cursor, oid)
        all_bases_safe = bool(bases)
        for base in bases:
            base_oid, kind, rls_enabled, _ = base
            if kind not in ("r", "p") or rls_enabled is not True:
                all_bases_safe = False
                continue
            cursor.execute(
                "SELECT polcmd,pg_catalog.pg_get_expr(polqual,polrelid),"
                " polpermissive,"
                " EXISTS (SELECT 1 FROM unnest(polroles) AS r(oid)"
                " WHERE r.oid=0 OR r.oid=("
                " SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s)"
                " OR pg_catalog.pg_has_role("
                " (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s),"
                " r.oid,'MEMBER'))"
                " FROM pg_catalog.pg_policy WHERE polrelid=%s",
                (ROLE,ROLE,base_oid),
            )
            # Deny any other permissive policy applicable to the CRM role,
            # including PUBLIC. A policy for another non-member role does
            # not extend this reader's access.
            active = [
                (expression, permissive)
                for command,expression,permissive,applies in cursor.fetchall()
                if command in ("r","*") and applies
            ]
            if not active or not any(permissive for _,permissive in active):
                all_bases_safe = False
            for expression, permissive in active:
                if not permissive:
                    continue
                allowed_buyer = re.search(
                    r"\b(?:tenant_id|org_id)\s*=\s*(?:public\.)?"
                    r"empire_current_tenant_id\s*\(\s*\)", expression or "", re.I,
                )
                if label=="prospects" and "empire_crm_prospect_authorized" in (expression or ""):
                    _block(
                        issues,helper_safe,
                        "GUARDED_PROSPECT_SCOPE_FUNCTION_NOT_VERIFIED",
                    )
                allowed_prospect = (
                    helper_safe and label=="prospects" and re.search(
                        r"(?:public\.)?empire_crm_prospect_authorized\s*"
                        r"\(\s*id\s*\)",expression or "",re.I
                    )
                )
                if (
                    not isinstance(expression,str)
                    or re.search(r"\bOR\b|(?<!IS )\bNOT\b",expression,re.I)
                    or not (allowed_buyer or allowed_prospect)
                ):
                    all_bases_safe = False
        _block(issues, all_bases_safe, f"{label.upper()}_BASE_RLS_NOT_VERIFIED")
        details[label] = {
            "present": True, "columns_complete": complete,
            "security_invoker": invoker,
            "base_rls_verified": all_bases_safe,
            "role_select_only": select_only,
        }
    source_schema = inspect_source_schema(cursor)
    return {
        "schema": "empire.revenue_crm_live_catalog_preflight.v1",
        "status": "CATALOG_PRECONDITIONS_VERIFIED" if not issues else "BLOCKED",
        "source_schema": source_schema,
        "blockers": sorted(set(issues)),
        "role_safe": role_safe,
        "trusted_tenant_function_present": function is not None and function[0] is True,
        "views": details,
        "application_login_tenant_authority_verified": False,
        "actual_cross_tenant_read_verified": False,
        "buyer_authenticated": False,
        "public_api_activation_authorized": False,
        "no_data_rows_read": True,
        "execution_authority": "none",
    }


def run() -> int:
    dsn = os.getenv("EMPIREDB_DSN", "").strip()
    if not dsn:
        report = {
            "schema": "empire.revenue_crm_live_catalog_preflight.v1",
            "status": "CONNECTION_NOT_CONFIGURED",
            "blockers": ["APPROVED_DATABASE_CONNECTION_UNAVAILABLE"],
            "public_api_activation_authorized": False,
            "no_data_rows_read": True,
            "execution_authority": "none",
        }
    else:
        try:
            import psycopg
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout='5000ms'")
                    report = inspect_crm_catalog(cursor)
        except Exception:
            report = {
                "schema": "empire.revenue_crm_live_catalog_preflight.v1",
                "status": "CONNECTION_OR_CATALOG_ACCESS_FAILED",
                "blockers": ["DATABASE_CATALOG_PROBE_UNAVAILABLE"],
                "public_api_activation_authorized": False,
                "no_data_rows_read": True,
                "execution_authority": "none",
            }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "CATALOG_PRECONDITIONS_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(run())
