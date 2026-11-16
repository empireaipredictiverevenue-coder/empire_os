"""Authenticated source preflight for the existing Predictive Revenue engine.

Never promotes customer revenue or a forecast's accuracy. Uses only the
pre-existing restricted EmpireDB registry and completed-day census readers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_revenue_tenant_registry_inspector import (
    inspect_tenant_bound_predictive_registry,
)
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census

SCHEMA = "empire.predictive_revenue.authenticated_source_preflight.v1"


def _tenant_is_canonical(value: str) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def review_authenticated_sources(
    *, tenant_id: str | None, registry_dsn: str | None,
    census_dsn: str | None, as_of: datetime,
    registry_reader: Callable[..., dict[str, Any]] = inspect_tenant_bound_predictive_registry,
    census_reader: Callable[..., dict[str, Any]] = read_daily_revenue_census,
) -> dict[str, Any]:
    """A single attempt per dedicated reader; no credentials, tenant, rows in output."""
    if type(as_of) is not datetime or as_of.utcoffset() is None:
        raise ValueError("UTC-aware source evaluation time required")
    now = as_of.astimezone(timezone.utc)
    # Completed yesterday is not proof its financial close has finalized.
    day: date = now.date() - timedelta(days=1)
    scoped = _tenant_is_canonical(tenant_id)
    native_registry_reader = registry_reader is inspect_tenant_bound_predictive_registry
    native_census_reader = census_reader is read_daily_revenue_census
    registry_attempted = bool(scoped and isinstance(registry_dsn, str) and registry_dsn.strip())
    census_attempted = bool(scoped and isinstance(census_dsn, str) and census_dsn.strip())
    result = {
        "schema_version": SCHEMA,
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "status": "NO_VERIFIED_CUSTOMER_FORECAST_OUTCOME_PAIR",
        "original_restricted_registry_reader_reused": native_registry_reader and registry_attempted,
        "original_restricted_day_census_reader_reused": native_census_reader and census_attempted,
        "registry_restricted_read_attempted": registry_attempted,
        "census_restricted_read_attempted": census_attempted,
        "reader_tenant_scope_input_valid": scoped,
        "registry_source_status": "NOT_ATTEMPTED",
        "registry_scoped_rows_observed": None,
        "registry_reader_authenticated_session": False,
        "registry_immutable_timestamp_custody_verified": False,
        "census_source_status": "NOT_ATTEMPTED",
        "census_day": day.isoformat(),
        "census_tenant_events_observed": None,
        "census_reader_authenticated_session": False,
        "daily_revenue_census_finality_verified": False,
        "independently_verified_forecast_actual_pairs": 0,
        "model_calibration_ready": False,
        "customer_revenue_amount_verified": False,
        "source_credentials_exposed": False,
        "raw_financial_rows_exported": False,
        "tenant_id_exported": False,
        "database_writes": False,
        "model_weights_modified": False,
        "customer_release_authorized": False,
        "execution_authority": "none",
    }
    if not scoped:
        result["registry_source_status"] = "CANONICAL_TENANT_SCOPE_UNAVAILABLE"
        result["census_source_status"] = "CANONICAL_TENANT_SCOPE_UNAVAILABLE"
        return result
    if not isinstance(registry_dsn, str) or not registry_dsn.strip():
        result["registry_source_status"] = "DEDICATED_REGISTRY_CREDENTIAL_UNAVAILABLE"
    else:
        try:
            registry = registry_reader(
                dsn=registry_dsn, tenant_id=tenant_id, as_of=now, limit=100,
            )
            if (type(registry) is not dict
                or registry.get("schema_version") !=
                    "empire.predictive_revenue.tenant_registry_inspection.v1"
                or registry.get("mode") != "OBSERVE"
                or registry.get("execution_authority") != "none"
                or registry.get("trusted_session_user_tenant_matched") is not True
                or registry.get("reader_nologin_noinherit_nobypassrls_verified") is not True
                or registry.get("forecast_registry_force_rls_verified") is not True
                or registry.get("status") not in (
                    "TENANT_BOUND_REGISTRY_ROWS_OBSERVED_UNVERIFIED",
                    "REGISTRY_EMPTY_COVERAGE_UNKNOWN_HOLD",
                    "REGISTRY_READ_BOUND_REACHED_HOLD",
                )
                or registry.get("original_forecast_immutable_registration_verified") is not False
                or registry.get("financial_actuals_verified") is not False
                or type(registry.get("observed_row_count")) is not int
                or not 0 <= registry["observed_row_count"] <= 100):
                raise ValueError("registry proof inconsistent")
            result["registry_source_status"] = (
                registry["status"] if native_registry_reader
                else "INJECTED_READER_CONTRACT_TEST_ONLY"
            )
            result["registry_scoped_rows_observed"] = (
                registry["observed_row_count"] if native_registry_reader else None
            )
            result["registry_reader_authenticated_session"] = native_registry_reader
        except Exception:
            result["registry_source_status"] = "REGISTRY_RESTRICTED_READ_OR_POLICY_FAILED"
    if not isinstance(census_dsn, str) or not census_dsn.strip():
        result["census_source_status"] = "DEDICATED_CENSUS_CREDENTIAL_UNAVAILABLE"
    else:
        try:
            census = census_reader(
                day_utc=day, tenant_id=tenant_id, as_of=now,
                dsn=census_dsn, require_session_tenant_binding=True,
            )
            if (type(census) is not dict
                or census.get("schema_version") !=
                    "empire.predictive_revenue.daily_census_candidate.v1"
                or census.get("mode") != "OBSERVE"
                or census.get("execution_authority") != "none"
                or census.get("observed_utc_date") != day.isoformat()
                or census.get("database_session_tenant_identity_matched") is not True
                or census.get("status") not in (
                    "DAY_SOURCE_CENSUS_CANDIDATE",
                    "DAY_CENSUS_INCOMPLETE_HOLD",
                )
                or census.get("daily_revenue_census_verified") is not False
                or census.get("ledger_backfill_finality_attested") is not False
                or census.get("eligible_for_revenue_forecast_calibration") is not False
                or type(census.get("tenant_event_count")) is not int
                or not 0 <= census["tenant_event_count"] <= 1_000_000_000):
                raise ValueError("census proof inconsistent")
            result["census_source_status"] = (
                census["status"] if native_census_reader
                else "INJECTED_READER_CONTRACT_TEST_ONLY"
            )
            result["census_tenant_events_observed"] = (
                census["tenant_event_count"] if native_census_reader else None
            )
            result["census_reader_authenticated_session"] = native_census_reader
        except Exception:
            result["census_source_status"] = "CENSUS_RESTRICTED_READ_OR_POLICY_FAILED"
    return result
