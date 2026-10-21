"""Authenticated EmpireDB CATALOGUE-ONLY review of the dedicated conversion registry.

Never SELECTs original forecast rows. Presence of tables, roles and functions
does NOT prove a prospective immutable receipt, correct isolation, training
data, source-owner approval, or customer forecast eligibility.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from empire_os.predictive_tenant_outcome_reader_preflight import (
    IDENTITY_SQL, ROLE_SQL, READER_ROLE, _role,
)

SCHEMA = "empire.predictive_revenue.original_conversion_catalogue_probe.v1"
ROLE_NAMES = (
    "empire_original_conversion_prediction_writer",
    "empire_original_conversion_prediction_reader",
)
TABLE = "original_conversion_predictions"
EXPECTED_COLS = frozenset((
    "id", "tenant_id", "prediction_ref", "opportunity_key",
    "prediction_type", "predicted_probability", "model_name",
    "model_version", "proposed_at", "horizon_until", "source_evidence",
    "prediction_json", "client_payload_sha256", "recorded_at",
))
OBJECT_SQL = """
SELECT pg_catalog.to_regclass('public.original_conversion_predictions') IS NOT NULL,
       pg_catalog.to_regprocedure('public.record_original_conversion_prediction_v1(text,text,jsonb,text)') IS NOT NULL,
       pg_catalog.to_regprocedure('public.read_original_conversion_prediction_v1(text,text)') IS NOT NULL,
       pg_catalog.to_regprocedure('public.reject_original_conversion_prediction_change_v1()') IS NOT NULL
""".strip()
ROLE_INVENTORY_SQL = """
SELECT rolname::text, rolcanlogin, rolsuper, rolbypassrls,
       rolinherit, rolcreatedb, rolcreaterole, rolreplication,
       pg_catalog.pg_has_role(session_user, oid, 'MEMBER')
FROM pg_catalog.pg_roles
WHERE rolname=ANY(%s::text[])
ORDER BY rolname
""".strip()
TABLE_SQL = """
SELECT c.relrowsecurity, c.relforcerowsecurity,
       pg_catalog.has_table_privilege(current_user,c.oid,'SELECT'),
       pg_catalog.has_table_privilege(current_user,c.oid,'INSERT'),
       pg_catalog.has_table_privilege(current_user,c.oid,'UPDATE'),
       pg_catalog.has_table_privilege(current_user,c.oid,'DELETE')
FROM pg_catalog.pg_class c
WHERE c.oid=pg_catalog.to_regclass('public.original_conversion_predictions')
""".strip()
COLUMN_SQL = """
SELECT a.attname::text
FROM pg_catalog.pg_attribute a
WHERE a.attrelid=pg_catalog.to_regclass('public.original_conversion_predictions')
  AND a.attnum>0 AND NOT a.attisdropped
ORDER BY a.attnum
""".strip()
POLICY_SQL = """
SELECT policyname::text, cmd::text, roles::text[], qual::text,
       with_check::text
FROM pg_catalog.pg_policies
WHERE schemaname='public' AND tablename='original_conversion_predictions'
ORDER BY policyname
""".strip()
ROUTINE_SQL = """
SELECT p.proname::text, p.prosecdef, p.provolatile::text,
       pg_catalog.has_function_privilege(current_user,p.oid,'EXECUTE')
FROM pg_catalog.pg_proc p
WHERE p.oid=ANY(ARRAY[
    pg_catalog.to_regprocedure('public.record_original_conversion_prediction_v1(text,text,jsonb,text)'),
    pg_catalog.to_regprocedure('public.read_original_conversion_prediction_v1(text,text)'),
    pg_catalog.to_regprocedure('public.reject_original_conversion_prediction_change_v1()')
]::oid[])
ORDER BY p.proname
""".strip()
TRIGGER_SQL = """
SELECT t.tgname::text,t.tgenabled::text,t.tgisinternal
FROM pg_catalog.pg_trigger t
WHERE t.tgrelid=pg_catalog.to_regclass('public.original_conversion_predictions')
ORDER BY t.tgname
""".strip()


class ConversionCatalogueHold(ValueError):
    """A safe diagnostic; never expose credentials, private DB errors or tenant."""


def _metadata_report(
    *, objects: Any, roles: Any, table: Any, columns: Any,
    policies: Any, routines: Any, triggers: Any,
) -> dict[str, Any]:
    if (type(objects) not in (tuple,list) or len(objects)!=4
            or any(type(v) is not bool for v in objects)
            or type(roles) is not list or len(roles)>4
            or type(columns) is not list or len(columns)>40
            or type(policies) is not list or len(policies)>8
            or type(routines) is not list or len(routines)>6
            or type(triggers) is not list or len(triggers)>5):
        raise ConversionCatalogueHold("unexpected original registry metadata shape")

    role_inventory={}
    for item in roles:
        if (type(item) not in (tuple,list) or len(item)!=9
                or type(item[0]) is not str or item[0] not in ROLE_NAMES
                or item[0] in role_inventory
                or any(type(value) is not bool for value in item[1:])):
            raise ConversionCatalogueHold("original role metadata invalid")
        role_inventory[item[0]] = tuple(item[1:])
    column_names=[]
    for col in columns:
        if (type(col) not in (tuple,list) or len(col)!=1
                or type(col[0]) is not str or col[0] in column_names):
            raise ConversionCatalogueHold("original column metadata invalid")
        column_names.append(col[0])
    if table is not None and (
        type(table) not in (tuple,list) or len(table)!=6
        or any(type(v) is not bool for v in table)
    ):
        raise ConversionCatalogueHold("table security metadata invalid")
    for item in policies:
        if (type(item) not in (tuple,list) or len(item)!=5
                or type(item[0]) is not str or type(item[1]) is not str
                or type(item[2]) is not list):
            raise ConversionCatalogueHold("policy metadata invalid")
    for item in routines:
        if (type(item) not in (tuple,list) or len(item)!=4
                or type(item[0]) is not str
                or any(type(v) is not bool for v in (item[1],item[3]))
                or type(item[2]) is not str):
            raise ConversionCatalogueHold("routine metadata invalid")
    for item in triggers:
        if (type(item) not in (tuple,list) or len(item)!=3
                or type(item[0]) is not str or type(item[1]) is not str
                or type(item[2]) is not bool):
            raise ConversionCatalogueHold("trigger metadata invalid")

    absent = (
        not any(objects) and not roles and table is None
        and not columns and not policies and not routines and not triggers
    )
    role_safe = (len(role_inventory)==2 and all(
        v == (False,False,False,False,False,False,False,False)
        for v in role_inventory.values()
    ))
    table_safe = (tuple(table)==(True,True,False,False,False,False)
                  if table is not None else False)
    expected_policies = {
        "original_conversion_migrator_tenant_read":
            ("SELECT",["empiredb_migrator"],"empire_current_tenant_id","tenant_id"),
        "original_conversion_migrator_tenant_insert":
            ("INSERT",["empiredb_migrator"],"empire_current_tenant_id","tenant_id"),
    }
    policy_safe=False
    if len(policies)==2:
        found={}
        for item in policies:
            name,cmd,applies,qual,check=item
            if name in found or name not in expected_policies:
                break
            found[name]=item
        else:
            policy_safe=set(found)==set(expected_policies)
            if policy_safe:
                for name,(cmd,applies,scope,tenant) in expected_policies.items():
                    actual=found[name]
                    expression=actual[3] if cmd=="SELECT" else actual[4]
                    policy_safe &= (
                        actual[1]==cmd and actual[2]==applies
                        and isinstance(expression,str)
                        and scope in expression and tenant in expression
                    )
    names={
        "record_original_conversion_prediction_v1":(True,"v",False),
        "read_original_conversion_prediction_v1":(True,"s",False),
        "reject_original_conversion_prediction_change_v1":(False,"v",False),
    }
    routine_safe=(len(routines)==3 and
                  all((r[1],r[2],r[3])==names.get(r[0])
                      for r in routines))
    trigger_safe=(triggers==[
        ("original_conversion_prediction_immutable","O",False)
    ])
    shape_ready = (
        all(objects) and role_safe and table_safe
        and set(column_names)==EXPECTED_COLS and policy_safe
        and routine_safe and trigger_safe
    )
    if absent:
        status="DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED"
    elif shape_ready:
        status="DEDICATED_CONVERSION_OBJECTS_PRESENT_REVIEW_REQUIRED"
    else:
        status="DEDICATED_CONVERSION_PARTIAL_OR_SECURITY_DRIFT_HOLD"
    return {
        "status":status,
        "object_presence":{
            "dedicated_table":objects[0],
            "dedicated_write_function":objects[1],
            "dedicated_read_function":objects[2],
            "immutability_trigger_function":objects[3],
        },
        "expected_dedicated_roles_present":len(role_inventory),
        "dedicated_roles_metadata_safe_shape":role_safe,
        "table_force_rls_and_no_reader_dml_grants":table_safe,
        "expected_column_inventory_match":set(column_names)==EXPECTED_COLS,
        "expected_tenant_scoped_policy_metadata_match":policy_safe,
        "expected_routine_metadata_match":routine_safe,
        "expected_immutability_trigger_metadata_match":trigger_safe,
        "catalogue_metadata_completeness_verified":True,
        "original_registry_metadata_candidate":shape_ready,
    }


def review_original_conversion_catalogue(
    *, dsn: str, connect_factory: Callable[...,Any] | None = None,
) -> dict[str, Any]:
    if type(dsn) is not str or not dsn.strip():
        raise ConversionCatalogueHold("original credential missing")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError:
            raise ConversionCatalogueHold("database driver unavailable") from None
        connect_factory=psycopg.connect
    try:
        with connect_factory(dsn,connect_timeout=5) as connection:
            with connection.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE " + READER_ROLE)
                cur.execute(IDENTITY_SQL)
                identity=cur.fetchone()
                if (type(identity) not in (tuple,list) or len(identity)!=5):
                    raise ConversionCatalogueHold("original session not authenticated")
                database, readonly, login, role, tenant=identity
                if (database!="empiredb" or readonly!="on"
                        or not isinstance(login,str)
                        or login in ("", "postgres",READER_ROLE)
                        or role!=READER_ROLE or type(tenant) is not str):
                    raise ConversionCatalogueHold("original session invalid")
                try:
                    if str(UUID(tenant))!=tenant:
                        raise ValueError("invalid tenant")
                except (ValueError,TypeError):
                    raise ConversionCatalogueHold("original scoped session missing") from None
                cur.execute(ROLE_SQL,(login,))
                if not _role(cur.fetchone(),login=True):
                    raise ConversionCatalogueHold("login authority invalid")
                cur.execute(ROLE_SQL,(READER_ROLE,))
                if not _role(cur.fetchone(),login=False):
                    raise ConversionCatalogueHold("reader authority invalid")
                cur.execute(OBJECT_SQL); objects=cur.fetchone()
                cur.execute(ROLE_INVENTORY_SQL,(list(ROLE_NAMES),)); roles=cur.fetchall()
                cur.execute(TABLE_SQL); table=cur.fetchone()
                cur.execute(COLUMN_SQL); columns=cur.fetchall()
                cur.execute(POLICY_SQL); policies=cur.fetchall()
                cur.execute(ROUTINE_SQL); routines=cur.fetchall()
                cur.execute(TRIGGER_SQL); triggers=cur.fetchall()
        result=_metadata_report(
            objects=objects,roles=roles,table=table,columns=columns,
            policies=policies,routines=routines,triggers=triggers,
        )
    except Exception:
        raise ConversionCatalogueHold("original conversion catalogue not readable") from None
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "canonical_database":"EmpireDB",
        "authenticated_tenant_session":True,
        "transaction_read_only_verified":True,
        **result,
        "old_directional_predictive_forecasts_not_substituted":True,
        "original_conversion_rows_queried":False,
        "original_conversion_records_admitted":False,
        "real_customer_outcomes_proven":False,
        "forecast_immutable_registration_proven":False,
        "original_forecast_before_outcome_proven":False,
        "scientific_training_or_customer_forecast_authorized":False,
        "new_roles_grants_ddl_migrations_or_credentials":False,
        "database_writes":False,
        "execution_authority":"none",
    }
