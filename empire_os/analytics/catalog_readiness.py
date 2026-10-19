"""Read-only, catalog-only Analytics054/055 deployment authority review.

No customer records, session tables, campaign data, or consent rows read.
No mutations, DDL, role grants, or credential files. Outputs boolean
schema/role facts only; does NOT imply founder or privacy activation.
"""
from __future__ import annotations
from typing import Any

SCHEMA="empire.analytics.live_catalog_boundary.v1"

# Fixed SQL referencing only pg_catalog. No user supplied identifiers.
CATALOG_SQL = """
SELECT pg_catalog.jsonb_build_object(
  'database_name_correct', current_database() = 'empiredb',
  'not_recovery_replica', NOT pg_catalog.pg_is_in_recovery(),
  'migrator_role_safe', EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
      AND NOT rolsuper AND NOT rolbypassrls),
  'table_count', (
      SELECT count(*) FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relkind='r'
      AND c.relname IN (
        'empire_analytics_sessions',
        'empire_analytics_consent_decisions',
        'empire_analytics_event_receipts',
        'empire_analytics_erasure_audit')
  ),
  'session_table', to_regclass('public.empire_analytics_sessions') IS NOT NULL,
  'consent_table', to_regclass('public.empire_analytics_consent_decisions') IS NOT NULL,
  'event_table', to_regclass('public.empire_analytics_event_receipts') IS NOT NULL,
  'audit_table', to_regclass('public.empire_analytics_erasure_audit') IS NOT NULL,
  'all_present_tables_forced_rls', COALESCE((
       SELECT bool_and(c.relrowsecurity AND c.relforcerowsecurity)
       FROM pg_catalog.pg_class c
       JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='public' AND c.relkind='r'
       AND c.relname IN (
        'empire_analytics_sessions',
        'empire_analytics_consent_decisions',
        'empire_analytics_event_receipts',
        'empire_analytics_erasure_audit')
  ), false),
  'all_present_table_owners_migrator', COALESCE((
       SELECT bool_and(r.rolname='empiredb_migrator')
       FROM pg_catalog.pg_class c
       JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
       JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
       WHERE n.nspname='public' AND c.relkind='r'
       AND c.relname IN (
        'empire_analytics_sessions',
        'empire_analytics_consent_decisions',
        'empire_analytics_event_receipts',
        'empire_analytics_erasure_audit')
  ), false),
  'erasure_function_present', to_regprocedure(
       'public.empire_analytics_erase_session(uuid,text,text,text,text)'
  ) IS NOT NULL,
  'erasure_function_security_definer_migrator', EXISTS(
       SELECT 1 FROM pg_catalog.pg_proc p
       JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
       WHERE p.oid=to_regprocedure(
          'public.empire_analytics_erase_session(uuid,text,text,text,text)')
       AND p.prosecdef AND r.rolname='empiredb_migrator'
  ),
  'erasure_function_public_execute', CASE
       WHEN to_regprocedure(
         'public.empire_analytics_erase_session(uuid,text,text,text,text)')
         IS NULL THEN false
       ELSE has_function_privilege(
           'public', 'public.empire_analytics_erase_session(uuid,text,text,text,text)',
           'EXECUTE')
  END,
  'maintenance_login_exists', EXISTS(
       SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empire_analytics_maintenance_login'
  ),
  'maintenance_login_credential_active', EXISTS(
       SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empire_analytics_maintenance_login'
         AND rolcanlogin
  ),
  'maintenance_execute_granted', CASE
       WHEN to_regrole('empire_analytics_maintenance_login') IS NULL
        OR to_regprocedure(
          'public.empire_analytics_erase_session(uuid,text,text,text,text)')
            IS NULL THEN false
       ELSE has_function_privilege(
          'empire_analytics_maintenance_login',
          'public.empire_analytics_erase_session(uuid,text,text,text,text)',
          'EXECUTE')
  END
)::text
"""


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version":SCHEMA,
        "status":reason,
        "mode":"READ_ONLY",
        "database_catalog_observed":False,
        "canonical_empiredb":True,
        "analytics054_production_deployed_verified":False,
        "analytics055_production_deployed_verified":False,
        "maintenance_activation_authorised":False,
        "website_analytics_consent_verified":False,
        "live_visitor_sessions_verified":False,
        "schema_applied_by_probe":False,
        "database_writes":False,
        "customer_records_read":False,
        "service_restarted":False,
        "public_site_changed":False,
        "execution_authority":"NONE",
    }


def summarize_facts(facts: Any, *, expected_db: str = "empiredb") -> dict[str,Any]:
    """Trust nothing until exact object shape, ownership and RLS match."""
    if not isinstance(facts,dict):
        return _held("HELD_ANALYTICS_CATALOG_UNREADABLE")
    required={
        "database_name_correct", "not_recovery_replica","migrator_role_safe",
        "table_count", "session_table", "consent_table", "event_table",
        "audit_table", "all_present_tables_forced_rls",
        "all_present_table_owners_migrator", "erasure_function_present",
        "erasure_function_security_definer_migrator",
        "erasure_function_public_execute","maintenance_login_exists",
        "maintenance_login_credential_active","maintenance_execute_granted",
    }
    if set(facts) != required:
        return _held("HELD_ANALYTICS_CATALOG_SHAPE_DRIFT")
    if expected_db=="empire_analytics_fixture":
        db_is_correct = True
    elif expected_db=="empiredb":
        db_is_correct = facts["database_name_correct"] is True
    else:
        return _held("HELD_ANALYTICS_INVALID_EXPECTED_DATABASE")
    if not db_is_correct or facts["not_recovery_replica"] is not True:
        return _held("HELD_ANALYTICS_WRONG_PRIMARY_CATALOG")
    table_names=["session_table","consent_table","event_table","audit_table"]
    base=all(facts[key] is True for key in table_names[:3])
    audit=facts["audit_table"] is True
    count=facts["table_count"]
    if not type(count) is int or count not in (0,3,4):
        return _held("HELD_ANALYTICS_OBJECT_COLLISION")
    if count==0 and all(facts[key] is False for key in table_names)         and facts["erasure_function_present"] is False:
        state="ANALYTICS054_055_NOT_DEPLOYED_IN_OBSERVED_CATALOG"
        base_ok=False
        audit_ok=False
    elif count==3 and base and not audit and facts["erasure_function_present"] is False:
        state="ANALYTICS054_PRESENT_055_NOT_DEPLOYED"
        base_ok=True
        audit_ok=False
    elif count==4 and base and audit and facts["erasure_function_present"] is True         and facts["erasure_function_security_definer_migrator"] is True:
        state="ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD"
        base_ok=True
        audit_ok=True
    else:
        return _held("HELD_ANALYTICS_OBJECT_SHAPE_INCONSISTENT")
    if count and not(
        facts["migrator_role_safe"] is True and
        facts["all_present_tables_forced_rls"] is True and
        facts["all_present_table_owners_migrator"] is True
    ):
        return _held("HELD_ANALYTICS_OWNER_OR_RLS_DRIFT")
    if (facts["erasure_function_public_execute"] is not False or
        facts["maintenance_execute_granted"] is not False or
        facts["maintenance_login_credential_active"] is not False or
        facts["maintenance_login_exists"] is not False):
        return _held("HELD_ANALYTICS_UNAPPROVED_RUNTIME_AUTHORITY")
    return {
        **_held(state),
        "database_catalog_observed":True,
        "analytics054_production_deployed_verified":base_ok if expected_db=="empiredb" else False,
        "analytics055_production_deployed_verified":audit_ok if expected_db=="empiredb" else False,
        "fixture_schema_present":base_ok if expected_db=="empire_analytics_fixture" else False,
        "fixture_erasure_present":audit_ok if expected_db=="empire_analytics_fixture" else False,
        "table_count_catalog":count,
        "no_public_erasure_execute_verified":not facts["erasure_function_public_execute"],
        "maintenance_role_not_activated_verified":not facts["maintenance_login_exists"],
    }


def inspect_connection(conn: Any, *, expected_db:str="empiredb") -> dict[str,Any]:
    """Caller supplies an existing read-only connection to exact database.

    The CLI creates its own forced read-only transaction and never
    accepts user-provided SQL, a DSN, URL, or list of table names.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout='4000ms'")
            cur.execute("SET LOCAL lock_timeout='1000ms'")
            cur.execute(CATALOG_SQL)
            row=cur.fetchone()
            cur.execute("ROLLBACK")
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return _held("HELD_ANALYTICS_LOCAL_CATALOG_QUERY_FAILED")
    if not row or len(row)!=1:
        return _held("HELD_ANALYTICS_LOCAL_CATALOG_EMPTY")
    import json
    try:
        facts=json.loads(row[0])
    except (ValueError,TypeError):
        return _held("HELD_ANALYTICS_LOCAL_CATALOG_BAD_RESPONSE")
    return summarize_facts(facts,expected_db=expected_db)
