#!/usr/bin/env python3
"""EmpireDB source catalogue truth for Predictive Revenue.

Use only as the existing founder-authorised PostgreSQL administrator in
an explicitly read-only transaction. Metadata booleans only; no tenant rows,
customer PII, credentials, forecast values, privilege changes or DDL.

The existing REV052 login certifies one event reader, not forecast registry
or day-census installation. This checker makes that distinction explicit.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

from scripts.provision_revenue_event_evidence_login_20261018 import pg

SCHEMA = "empire.predictive_revenue.original_source_catalog_readonly.v1"
QUERY = """BEGIN READ ONLY;
SET LOCAL statement_timeout='4000ms';
SET LOCAL lock_timeout='1000ms';
SELECT pg_catalog.jsonb_build_object(
  'correct_database',
    current_database()='empiredb' AND NOT pg_catalog.pg_is_in_recovery(),
  'tenant_resolver_exists',
    pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL,
  'rev052_single_event_reader_exists',
    pg_catalog.to_regprocedure('public.read_predictive_revenue_event_v1(uuid,text)') IS NOT NULL,
  'rev052_restricted_login_exists',
    EXISTS(SELECT 1 FROM pg_catalog.pg_roles
           WHERE rolname='empire_predictive_revenue_evidence_login'
           AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls),
  'forecast_registry_table_exists',
    pg_catalog.to_regclass('public.predictive_forecasts') IS NOT NULL,
  'forecast_registry_force_rls',
    COALESCE((SELECT relrowsecurity AND relforcerowsecurity
       FROM pg_catalog.pg_class
       WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')),FALSE),
  'forecast_registry_reader_role_safe',
    EXISTS(SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empire_predictive_registry_reader'
       AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls AND NOT rolinherit),
  'restricted_day_census_function_exists',
    pg_catalog.to_regprocedure('public.read_predictive_revenue_day_v1(date,text)') IS NOT NULL
)::text;
ROLLBACK;"""
FIELDS = (
    "correct_database",
    "tenant_resolver_exists",
    "rev052_single_event_reader_exists",
    "rev052_restricted_login_exists",
    "forecast_registry_table_exists",
    "forecast_registry_force_rls",
    "forecast_registry_reader_role_safe",
    "restricted_day_census_function_exists",
)


def review_catalog(*, admin_query: Callable[[str], str] = pg) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "CATALOG_UNAVAILABLE_HOLD",
        "catalogue_probe": "POSTGRESQL_READ_ONLY_METADATA",
        "catalogue_facts": None,
        "source_contracts_both_present": False,
        "founder_event_reader_separate_from_forecast_reader": True,
        "authenticated_forecast_rows_read": False,
        "customer_outcomes_read": False,
        "forecast_origin_attested": False,
        "forecast_accuracy_measurable": False,
        "requires_independent_tenant_session_after_catalogue": True,
        "database_writes": False,
        "role_changes": False,
        "ddl_executed": False,
        "customer_identity_exported": False,
        "execution_authority": "none",
    }
    try:
        raw = json.loads(admin_query(QUERY))
        if type(raw) is not dict or set(raw) != set(FIELDS):
            return result
        if any(type(raw[key]) is not bool for key in FIELDS):
            return result
        if not raw["correct_database"]:
            result["status"] = "WRONG_OR_UNTRUSTED_DATABASE_HOLD"
            return result
        result["catalogue_facts"] = {key: raw[key] for key in FIELDS}
        source_fields = (
            "tenant_resolver_exists",
            "forecast_registry_table_exists",
            "forecast_registry_force_rls",
            "forecast_registry_reader_role_safe",
            "restricted_day_census_function_exists",
        )
        result["source_contracts_both_present"] = all(raw[k] for k in source_fields)
        result["status"] = (
            "SOURCE_CATALOGUE_PRESENT_NOT_AUTHENTICATED"
            if result["source_contracts_both_present"]
            else "FORECAST_OR_CENSUS_SOURCE_CATALOGUE_INCOMPLETE"
        )
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    opts = parser.parse_args(argv)
    if not opts.read_only or os.geteuid() != 0:
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": "EXPLICIT_ROOT_READ_ONLY_SESSION_REQUIRED",
            "mode": "OBSERVE",
            "database_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2
    report = review_catalog()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "SOURCE_CATALOGUE_PRESENT_NOT_AUTHENTICATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
